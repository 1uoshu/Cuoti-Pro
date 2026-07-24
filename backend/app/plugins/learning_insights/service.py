from collections import Counter
from datetime import date, datetime, time, timedelta
from zlib import crc32

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.kernel.models import User
from app.plugins.assignment_grading.models import Assignment, Question
from app.plugins.layered_practice.models import PracticeQuestion, PracticeTask
from app.plugins.mastery_tracking.models import MasteryRecord
from app.plugins.stage_assessment.models import ExamQuestion, ExamTask
from app.plugins.wrong_question_book.models import WrongQuestion


PERIOD_DAYS = {
    "日报": 1,
    "周报": 7,
    "月报": 30,
    "学期报告": 180,
}

REVIEW_BUCKETS = (
    (1, "今天", "今日复习"),
    (7, "7天后", "巩固强化"),
    (14, "14天后", "中期回顾"),
    (30, "30天后", "长效记忆"),
)

REVIEW_BUCKET_RANGES = (
    ((0, 1), "今天"),
    ((2, 9), "7天后"),
    ((10, 21), "14天后"),
    ((22, 45), "30天后"),
)

ACTIVITY_LEVEL_THRESHOLDS = (0, 2, 4, 7)


def get_reports(db: Session, user: User, *, period: str | None, subject: str | None) -> list[dict]:
    periods = [period] if period else list(PERIOD_DAYS)
    subjects = [subject] if subject else _report_subjects(db, user)
    today = datetime.now().date()
    reports = [
        _build_report(db, user.id, report_period, report_subject, today)
        for report_period in periods
        for report_subject in subjects
    ]
    return sorted(reports, key=lambda item: (item["start_date"], item["subject"]), reverse=True)


def _report_subjects(db: Session, user: User) -> list[str]:
    subjects = set(
        db.scalars(
            select(Assignment.subject)
            .where(Assignment.user_id == user.id)
            .distinct()
        ).all()
    )
    if user.main_subject:
        subjects.add(user.main_subject)
    return sorted(subjects)


def _build_report(db: Session, user_id: int, period: str, subject: str, end_date: date) -> dict:
    start_date = end_date - timedelta(days=PERIOD_DAYS[period] - 1)
    questions = db.scalars(
        select(Question)
        .join(Assignment)
        .where(
            Assignment.user_id == user_id,
            Assignment.status == "completed",
            Assignment.subject == subject,
            Question.created_at >= datetime.combine(start_date, time.min),
            Question.created_at <= datetime.combine(end_date, time.max),
        )
    ).all()
    wrong_questions = db.scalars(
        select(WrongQuestion).where(
            WrongQuestion.user_id == user_id,
            WrongQuestion.subject == subject,
            WrongQuestion.created_at >= datetime.combine(start_date, time.min),
            WrongQuestion.created_at <= datetime.combine(end_date, time.max),
        )
    ).all()
    correct_count = sum(question.is_correct is True for question in questions)
    error_count = sum(question.is_correct is False for question in questions)
    total_count = len(questions)
    subject_counts = Counter(item.subject for item in wrong_questions)
    error_counts = Counter(_classify_error(item.wrong_reason) for item in wrong_questions)
    trend_start = end_date - timedelta(days=6)
    trend_counts = Counter(item.created_at.date() for item in wrong_questions if item.created_at.date() >= trend_start)
    trend_dates = [trend_start + timedelta(days=offset) for offset in range(7)]

    return {
        "id": crc32(f"{user_id}:{period}:{subject}:{end_date.isoformat()}".encode()) & 0x7FFFFFFF,
        "period": period,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "subject": subject,
        "stats": {
            "total_questions": total_count,
            "correct_questions": correct_count,
            "error_questions": error_count,
            "accuracy": round(correct_count / total_count * 100) if total_count else 0,
        },
        "trend": {
            "dates": [f"{item.month}/{item.day}" for item in trend_dates],
            "wrong_counts": [trend_counts[item] for item in trend_dates],
        },
        "subject_distribution": _percent_rows(subject_counts, "subject"),
        "error_types": _percent_rows(error_counts, "type"),
    }


def _classify_error(reason: str | None) -> str:
    text = (reason or "").strip()
    categories = (
        ("计算错误", ("计算", "运算")),
        ("概念不清", ("概念", "定义")),
        ("逻辑错误", ("逻辑", "推理")),
        ("审题失误", ("审题", "题意")),
    )
    for label, keywords in categories:
        if any(keyword in text for keyword in keywords):
            return label
    return "其他"


def _percent_rows(counts: Counter[str], label: str) -> list[dict]:
    total = sum(counts.values())
    if not total:
        return []
    return [
        {label: name, "wrong_count" if label == "subject" else "count": count, "percent": round(count / total * 100)}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def get_tracking_overview(db: Session, user: User) -> dict:
    mastery_records = db.scalars(
        select(MasteryRecord).where(MasteryRecord.user_id == user.id)
    ).all()
    overall_mastery = _weighted_mastery(mastery_records)

    today = datetime.now().date()
    today_count = db.scalar(
        select(func.count(WrongQuestion.id)).where(
            WrongQuestion.user_id == user.id,
            WrongQuestion.updated_at >= datetime.combine(today, time.min),
        )
    ) or 0

    streak_days = _streak_days(db, user.id)

    return {
        "overall_mastery": overall_mastery,
        "today_review_count": today_count,
        "streak_days": streak_days,
    }


def _weighted_mastery(records: list[MasteryRecord]) -> int:
    if not records:
        return 0
    weighted_total = 0.0
    weight_total = 0
    for record in records:
        weight = (record.correct_count or 0) + (record.wrong_count or 0)
        weighted_total += float(record.mastery_score or 0) * weight
        weight_total += weight
    if weight_total == 0:
        return 0
    return round(weighted_total / weight_total)


def _streak_days(db: Session, user_id: int) -> int:
    activity_dates = _activity_dates(db, user_id)
    today = datetime.now().date()
    streak = 0
    cursor = today
    while cursor in activity_dates:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


def _activity_dates(db: Session, user_id: int) -> set[date]:
    dates: set[date] = set()

    for column, owner_id in (
        (Assignment.created_at, Assignment.user_id),
        (PracticeTask.created_at, PracticeTask.user_id),
        (ExamTask.created_at, ExamTask.user_id),
        (WrongQuestion.created_at, WrongQuestion.user_id),
    ):
        rows = db.execute(
            select(func.date(column)).where(owner_id == user_id).distinct()
        ).all()
        dates.update(_coerce_date(row[0]) for row in rows)

    for child_column, parent, owner_id in (
        (Question.created_at, Assignment, Assignment.user_id),
        (PracticeQuestion.created_at, PracticeTask, PracticeTask.user_id),
        (ExamQuestion.created_at, ExamTask, ExamTask.user_id),
    ):
        rows = db.execute(
            select(func.date(child_column)).join(parent).where(owner_id == user_id).distinct()
        ).all()
        dates.update(_coerce_date(row[0]) for row in rows)

    return dates


def get_knowledge_graph(db: Session, user: User, *, subject: str | None) -> dict:
    query = select(MasteryRecord).where(MasteryRecord.user_id == user.id)
    if subject:
        query = query.where(MasteryRecord.subject == subject)
    records = db.scalars(query).all()
    nodes = [
        {
            "name": record.knowledge_point,
            "subject": record.subject,
            "mastery_score": round(float(record.mastery_score or 0)),
            "level": _mastery_level(record.mastery_score),
        }
        for record in records
    ]
    nodes.sort(key=lambda item: (-item["level"], item["mastery_score"]))
    return {"nodes": nodes}


def _mastery_level(score: float | None) -> int:
    score = float(score or 0)
    if score >= 80:
        return 1
    if score >= 60:
        return 2
    if score >= 40:
        return 3
    return 4


def get_review_schedule(db: Session, user: User, *, status: str | None) -> list[dict]:
    today = datetime.now().date()
    wrong_questions = db.scalars(
        select(WrongQuestion)
        .where(WrongQuestion.user_id == user.id)
        .order_by(WrongQuestion.created_at.desc())
    ).all()
    counts: Counter[str] = Counter()
    for item in wrong_questions:
        if not _matches_status(item.status, status):
            continue
        reference_date = item.updated_at.date() if item.updated_at else item.created_at.date()
        age = max((today - reference_date).days, 0)
        counts[_bucket_for_age(age)] += 1

    rows = []
    for _, stage, label in REVIEW_BUCKETS:
        rows.append(
            {
                "stage": stage,
                "label": label,
                "question_count": counts.get(stage, 0),
                "active": stage == "今天",
            }
        )
    return rows


def _matches_status(actual: str, requested: str | None) -> bool:
    if not requested or requested == "pending":
        return actual == "unreviewed"
    if requested == "overdue":
        return actual != "completed"
    if requested == "completed":
        return actual == "completed"
    return True


def _bucket_for_age(days: int) -> str:
    for (low, high), name in REVIEW_BUCKET_RANGES:
        if low <= days <= high:
            return name
    return "今天"


def get_activity_heatmap(db: Session, user: User, *, days: int) -> list[dict]:
    window_days = max(7, min(30, days))
    today = datetime.now().date()
    start_date = today - timedelta(days=window_days - 1)
    start_dt = datetime.combine(start_date, time.min)

    assignment_counts = {
        _coerce_date(row[0]): int(row[1])
        for row in db.execute(
            select(func.date(Question.created_at), func.count(Question.id))
            .join(Assignment)
            .where(Assignment.user_id == user.id, Question.created_at >= start_dt)
            .group_by(func.date(Question.created_at))
        ).all()
    }
    practice_counts = {
        _coerce_date(row[0]): int(row[1])
        for row in db.execute(
            select(func.date(PracticeQuestion.created_at), func.count(PracticeQuestion.id))
            .join(PracticeTask)
            .where(PracticeTask.user_id == user.id, PracticeQuestion.created_at >= start_dt)
            .group_by(func.date(PracticeQuestion.created_at))
        ).all()
    }
    exam_counts = {
        _coerce_date(row[0]): int(row[1])
        for row in db.execute(
            select(func.date(ExamQuestion.created_at), func.count(ExamQuestion.id))
            .join(ExamTask)
            .where(ExamTask.user_id == user.id, ExamQuestion.created_at >= start_dt)
            .group_by(func.date(ExamQuestion.created_at))
        ).all()
    }

    rows = []
    for offset in range(window_days):
        day = start_date + timedelta(days=offset)
        count = (
            assignment_counts.get(day, 0)
            + practice_counts.get(day, 0)
            + exam_counts.get(day, 0)
        )
        rows.append(
            {
                "date": f"{day.month}/{day.day}",
                "question_count": count,
                "level": _activity_level(count),
            }
        )
    return rows


def _activity_level(count: int) -> int:
    thresholds = ACTIVITY_LEVEL_THRESHOLDS
    for level, ceiling in enumerate(thresholds):
        if count <= ceiling:
            return level
    return 4


def _coerce_date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise TypeError(f"unsupported date value: {value!r}")


def get_profile_stats(db: Session, user: User) -> dict:
    total_errors = db.scalar(
        select(func.count(WrongQuestion.id)).where(WrongQuestion.user_id == user.id)
    ) or 0

    mastered_count = db.scalar(
        select(func.count(MasteryRecord.id)).where(
            MasteryRecord.user_id == user.id, MasteryRecord.mastery_score >= 80
        )
    ) or 0

    weak_count = db.scalar(
        select(func.count(MasteryRecord.id)).where(
            MasteryRecord.user_id == user.id, MasteryRecord.mastery_score < 40
        )
    ) or 0

    return {
        "total_errors": total_errors,
        "mastered_points": mastered_count,
        "weak_points": weak_count,
        "continuous_days": _streak_days(db, user.id),
    }


def get_profile_preferences(db: Session, user: User) -> dict:
    from app.plugins.learning_insights.models import UserPreferences, serialize_preferences

    record = db.scalar(select(UserPreferences).where(UserPreferences.user_id == user.id))
    return serialize_preferences(record)


def update_profile_preferences(db: Session, user: User, payload: dict) -> dict:
    from app.plugins.learning_insights.models import UserPreferences

    record = db.scalar(select(UserPreferences).where(UserPreferences.user_id == user.id))
    if record is None:
        record = UserPreferences(user_id=user.id)
        db.add(record)
    for field, value in payload.items():
        if value is None:
            continue
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return {
        "daily_goal": record.daily_goal,
        "review_time": record.review_time,
        "difficulty": record.difficulty,
        "weak_reminder": record.weak_reminder,
    }
