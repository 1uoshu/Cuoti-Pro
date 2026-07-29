# -*- coding: utf-8 -*-
"""直接跑通『上传图片→批改→错题归档』链路的测试脚本（不经过 Docker/HTTP）。

用真实 DeepSeek + Qwen3-VL API，逐阶段打印，定位到底哪一步断。
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import traceback
from pathlib import Path

# ── 环境准备（必须在 import app.* 之前） ─────────────────────────────
os.environ["APP_ENV"] = "test"
os.environ["REDIS_URL"] = "memory://"
os.environ["DATABASE_URL"] = "sqlite:///./storage/_test_pipeline.db"

# backend 目录加入 sys.path
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

TEST_IMAGE = r"C:\Users\宇怀\Desktop\作业2.png"
SUBJECT = "数学"
GRADE = "高二"


def _p(stage: str, msg: str = "") -> None:
    print(f"\n{'='*70}\n[{stage}] {msg}\n{'='*70}", flush=True)


async def main() -> int:
    # 干净的测试库
    test_db = BACKEND_DIR / "storage" / "_test_pipeline.db"
    test_db.parent.mkdir(parents=True, exist_ok=True)
    if test_db.exists():
        test_db.unlink()

    _p("SETUP", "构建 kernel context + 建表")
    # 导入全部模型，保证 create_all 覆盖所有表
    from app.kernel import models as _km  # noqa
    from app.plugins.assignment_grading import models as _am  # noqa
    from app.plugins.wrong_question_book import models as _wm  # noqa
    from app.plugins.wrong_question_book import feedback_models as _fm  # noqa
    from app.plugins.mastery_tracking import models as _mm  # noqa

    from app.kernel.context import build_kernel_context, set_kernel_context
    from app.kernel.database import Base, engine, SessionLocal
    from app.kernel.models import User

    context = build_kernel_context()
    set_kernel_context(context)
    Base.metadata.create_all(bind=engine)
    print("表已创建:", ", ".join(sorted(Base.metadata.tables.keys())))

    # 建测试用户
    with SessionLocal() as db:
        user = User(
            username="tester",
            password_hash="x",
            nickname="小测",
            grade=GRADE,
            main_subject=SUBJECT,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    print("测试用户 id =", user_id)

    # 拷贝图片到 storage
    img_src = Path(TEST_IMAGE)
    if not img_src.exists():
        print("!! 测试图片不存在:", img_src)
        return 1
    dest = BACKEND_DIR / "storage" / "uploads" / img_src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(img_src, dest)
    file_path = str(dest)
    print("图片已拷贝到:", file_path, f"({dest.stat().st_size} bytes)")

    # ── 阶段 1：图片 → data url ────────────────────────────────────
    _p("STAGE 1", "图片编码为 data url")
    from app.plugins.assignment_grading.workflow import _load_upload_as_data_urls
    try:
        data_urls = _load_upload_as_data_urls(file_path)
        print(f"data_urls 数量={len(data_urls)}, 首个长度={len(data_urls[0])}")
    except Exception:
        traceback.print_exc()
        return 1

    # ── 阶段 2：视觉 OCR（Qwen3-VL） ───────────────────────────────
    _p("STAGE 2", "Qwen3-VL 视觉识别")
    ocr_text = ""
    try:
        ocr_prompt = (
            f"请仔细阅读这份{SUBJECT}作业的全部页面，逐题提取题目原文、学生作答、"
            "以及任何可见的参考答案。按题目顺序输出。"
        )
        ocr_text = await context.capabilities.llm.vision_ocr(
            system_prompt="你是一个精确的作业识别助手。逐字提取图片中的文字内容。数学公式用 LaTeX 表示。",
            user_prompt=ocr_prompt,
            image_data_urls=data_urls,
            temperature=0.1,
            max_tokens=4000,
        )
        print("OCR 结果：\n", ocr_text)
    except Exception:
        print("!! OCR 失败：")
        traceback.print_exc()
        return 1

    # ── 阶段 3：DeepSeek 批改（python_verify） ─────────────────────
    _p("STAGE 3", "DeepSeek 推理判分")
    from app.plugins.assignment_grading.workflow import run_grading_workflow
    from app.plugins.assignment_grading.schemas import ModelGradePayload
    payload: ModelGradePayload | None = None
    try:
        payload = await run_grading_workflow(
            context, file_path, SUBJECT, GRADE, student_id=str(user_id)
        )
        print("批改成功。题目数 =", len(payload.questions))
        for q in payload.questions:
            print(f"  题{q.question_number}: is_correct={q.is_correct} | "
                  f"学生答={q.student_answer!r} 标答={q.correct_answer!r} | "
                  f"知识点={q.knowledge_point!r} | conf={q.confidence}")
    except Exception:
        print("!! 批改失败：")
        traceback.print_exc()
        return 1

    # ── 阶段 4：持久化 + 错题归档 ──────────────────────────────────
    _p("STAGE 4", "persist_grade_payload → 错题归档")
    from app.plugins.assignment_grading.models import Assignment
    from app.plugins.assignment_grading.service import persist_grade_payload
    from app.plugins.wrong_question_book.service import list_wrong_questions
    try:
        with SessionLocal() as db:
            assignment = Assignment(
                user_id=user_id,
                title="作业2",
                subject=SUBJECT,
                original_filename=img_src.name,
                file_path=file_path,
                status="processing",
            )
            db.add(assignment)
            db.flush()
            persist_grade_payload(context, db, assignment, payload)
            assignment.status = "completed"
            db.commit()
            aid = assignment.id
        print("持久化完成，assignment id =", aid)

        with SessionLocal() as db:
            wrongs = list_wrong_questions(db, user_id)
        _p("RESULT", f"错题本条目数 = {len(wrongs)}")
        for w in wrongs:
            q = w.get("question") or {}
            print(f"  错题#{w['id']} | 学科={w['subject']} | 知识点={w['knowledge_point']} | "
                  f"状态={w['status']} | 题号={q.get('question_number')} | "
                  f"学生答={q.get('student_answer')!r} 标答={q.get('correct_answer')!r}")
            print(f"       错因={w['wrong_reason']}")
        if wrongs:
            print("\n>>> 链路打通：错题已成功归档到错题本 <<<")
            return 0
        else:
            print("\n!! 批改成功但没有错题归档——检查 is_correct 是否全为 True")
            return 2
    except Exception:
        print("!! 持久化/归档失败：")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
