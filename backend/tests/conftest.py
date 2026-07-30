import os
from pathlib import Path


os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("DATABASE_URL", "sqlite:///./storage/test_smart_learning_agent.db")
os.environ.setdefault("POW_DIFFICULTY", "1")
# 测试进程内的 memory:// Redis 是全局单例、跨测试累积，滑窗限流计数不会在用例之间重置。
# 整套件的 /api 调用会累计越过默认 120/分钟阈值，导致后续用例随机拿到 429（PoW 字段随之缺失）。
# 与 POW_DIFFICULTY 同理，这里把限流阈值调高，保证测试隔离；生产仍用 config.py 默认值。
os.environ.setdefault("RATE_LIMIT_PER_IP", "1000000")
os.environ.setdefault("RATE_LIMIT_PER_USER", "1000000")
os.environ.setdefault("RATE_LIMIT_UPLOAD", "1000000")
os.environ["PLUGIN_MODULES"] = (
    "app.plugins.example,"
    "app.plugins.mastery_tracking,"
    "app.plugins.wrong_question_book,"
    "app.plugins.assignment_grading,"
    "app.plugins.layered_practice,"
    "app.plugins.stage_assessment,"
    "app.plugins.learning_dashboard,"
    "app.plugins.learning_insights"
)

test_database = Path(__file__).resolve().parents[1] / "storage" / "test_smart_learning_agent.db"
test_database.unlink(missing_ok=True)
