from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_user
from app.kernel.auth.schemas import LoginRequest, PasswordUpdateRequest, RegisterRequest, UserUpdateRequest
from app.kernel.auth.security import create_access_token, hash_password, verify_password
from app.kernel.auth.services import serialize_user
from app.kernel.context import get_kernel_context
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    audit = get_kernel_context().capabilities.audit
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
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname,
        grade=payload.grade,
        main_subject=payload.main_subject,
    )
    db.add(user)
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
    db.refresh(user)
    return ok({"user": serialize_user(user), "access_token": create_access_token(user.id), "token_type": "bearer"})


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    audit = get_kernel_context().capabilities.audit
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
    return ok({"user": serialize_user(user), "access_token": create_access_token(user.id), "token_type": "bearer"})


@router.post("/logout")
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_kernel_context().capabilities.audit.record(
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
