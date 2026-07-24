from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_user
from app.kernel.auth.pow import PowPurpose, create_challenge, verify_and_consume_challenge
from app.kernel.auth.schemas import LoginRequest, PasswordUpdateRequest, RegisterRequest, UserUpdateRequest
from app.kernel.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.kernel.auth.sessions import revoke_all_user_tokens, revoke_token, whitelist_token
from app.kernel.auth.services import serialize_user
from app.kernel.context import get_kernel_context
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok


router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_auth_response(user: User) -> dict:
    access_token = create_access_token(user.id)
    whitelist_token(get_kernel_context().capabilities.redis, access_token)
    return {"user": serialize_user(user), "access_token": access_token.value, "token_type": "bearer"}


@router.get("/pow/challenge")
def pow_challenge(request: Request, purpose: PowPurpose = Query(...)):
    context = get_kernel_context()
    return ok(create_challenge(context.capabilities.redis, context.settings, request, purpose))


@router.post("/register")
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    context = get_kernel_context()
    verify_and_consume_challenge(
        context.capabilities.redis,
        request,
        purpose="register",
        challenge_id=payload.pow_challenge_id,
        nonce=payload.pow_nonce,
    )
    audit = context.capabilities.audit
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing:
        audit.record(
            db,
            event_type="auth.register.conflict",
            actor_username=payload.username,
            outcome="failure",
            summary="Duplicate username during registration",
            request=request,
            commit=True,
        )
        raise HTTPException(status_code=409, detail="用户名已存在")
    is_first_user = db.scalar(select(User.id).limit(1)) is None
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname,
        grade=payload.grade,
        main_subject=payload.main_subject,
        role="admin" if is_first_user else "student",
        admin_slot=1 if is_first_user else None,
    )
    db.add(user)
    try:
        db.flush()
        audit.record(
            db,
            event_type="auth.register",
            actor=user,
            resource_type="user",
            resource_id=user.id,
            summary="Student account registered",
            metadata={"grade": user.grade, "main_subject": user.main_subject},
            request=request,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.scalar(select(User).where(User.username == payload.username)) is None:
            if is_first_user:
                user = User(
                    username=payload.username,
                    password_hash=hash_password(payload.password),
                    nickname=payload.nickname,
                    grade=payload.grade,
                    main_subject=payload.main_subject,
                    role="student",
                )
                db.add(user)
                db.flush()
                audit.record(
                    db,
                    event_type="auth.register",
                    actor=user,
                    resource_type="user",
                    resource_id=user.id,
                    summary="Student account registered after administrator race",
                    metadata={"grade": user.grade, "main_subject": user.main_subject},
                    request=request,
                )
                db.commit()
                db.refresh(user)
                return ok(_issue_auth_response(user))
            raise
        audit.record(
            db,
            event_type="auth.register.conflict",
            actor_username=payload.username,
            outcome="failure",
            summary="Duplicate username during concurrent registration",
            request=request,
            commit=True,
        )
        raise HTTPException(status_code=409, detail="用户名已存在")
    db.refresh(user)
    return ok(_issue_auth_response(user))


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    context = get_kernel_context()
    verify_and_consume_challenge(
        context.capabilities.redis,
        request,
        purpose="login",
        challenge_id=payload.pow_challenge_id,
        nonce=payload.pow_nonce,
    )
    audit = context.capabilities.audit
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        audit.record(
            db,
            event_type="auth.login.failed",
            actor_username=payload.username,
            outcome="failure",
            summary="Invalid username or password",
            request=request,
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    audit.record(
        db,
        event_type="auth.login",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        summary="User logged in",
        request=request,
        commit=True,
    )
    user.last_login_at = datetime.now()
    db.commit()
    db.refresh(user)
    return ok(_issue_auth_response(user))


@router.post("/logout")
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    context = get_kernel_context()
    revoke_token(context.capabilities.redis, request.state.access_token)
    context.capabilities.audit.record(
        db,
        event_type="auth.logout",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        summary="User logged out",
        request=request,
        commit=True,
    )
    return ok({"logged_out": True})


@router.get("/me")
def current_profile(user: User = Depends(get_current_user)):
    return ok(serialize_user(user))


@router.put("/me")
def update_profile(
    payload: UserUpdateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changed_fields = list(payload.model_dump(exclude_unset=True))
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    get_kernel_context().capabilities.audit.record(
        db,
        event_type="auth.profile.updated",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        summary="User profile updated",
        metadata={"changed_fields": changed_fields},
        request=request,
    )
    db.commit()
    db.refresh(user)
    return ok(serialize_user(user))


@router.put("/password")
def update_password(
    payload: PasswordUpdateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    audit = get_kernel_context().capabilities.audit
    if not verify_password(payload.current_password, user.password_hash):
        audit.record(
            db,
            event_type="auth.password.update.failed",
            actor=user,
            outcome="failure",
            resource_type="user",
            resource_id=user.id,
            summary="Current password did not match",
            request=request,
            commit=True,
        )
        raise HTTPException(status_code=400, detail="当前密码不正确")
    user.password_hash = hash_password(payload.new_password)
    revoke_all_user_tokens(get_kernel_context().capabilities.redis, user.id)
    audit.record(
        db,
        event_type="auth.password.updated",
        actor=user,
        resource_type="user",
        resource_id=user.id,
        summary="User password updated",
        request=request,
    )
    db.commit()
    return ok({"updated": True})
