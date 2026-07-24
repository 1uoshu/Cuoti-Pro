from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_user
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok
from app.plugins.learning_insights.schemas import ProfilePreferencesUpdate
from app.plugins.learning_insights.service import (
    get_activity_heatmap,
    get_knowledge_graph,
    get_profile_preferences,
    get_profile_stats,
    get_reports,
    get_review_schedule,
    get_tracking_overview,
    update_profile_preferences,
)


ReportPeriod = Literal["日报", "周报", "月报", "学期报告"]
ReviewStatus = Literal["pending", "overdue", "completed"]

router = APIRouter(tags=["learning-insights"])


@router.get("/reports")
def reports(
    period: ReportPeriod | None = None,
    subject: str | None = Query(default=None, min_length=1, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized_subject = subject.strip() if subject else None
    return ok(get_reports(db, user, period=period, subject=normalized_subject))


@router.get("/tracking/overview")
def tracking_overview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(get_tracking_overview(db, user))


@router.get("/knowledge-graph")
def knowledge_graph(
    subject: str | None = Query(default=None, min_length=1, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized_subject = subject.strip() if subject else None
    return ok(get_knowledge_graph(db, user, subject=normalized_subject))


@router.get("/tracking/review-schedule")
def review_schedule(
    status: ReviewStatus | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(get_review_schedule(db, user, status=status))


@router.get("/tracking/activity-heatmap")
def activity_heatmap(
    days: int = Query(default=14, ge=7, le=30),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(get_activity_heatmap(db, user, days=days))


@router.get("/profile/stats")
def profile_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(get_profile_stats(db, user))


@router.get("/profile/preferences")
def profile_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(get_profile_preferences(db, user))


@router.put("/profile/preferences")
def update_preferences(
    payload: ProfilePreferencesUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)
    return ok(update_profile_preferences(db, user, updates))
