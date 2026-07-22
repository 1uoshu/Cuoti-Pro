import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.kernel.auth.security import create_access_token, decode_access_token, seconds_until
from app.kernel.auth.sessions import token_is_active, whitelist_token
from app.kernel.config import get_settings
from app.kernel.context import get_kernel_context
from app.kernel.database import get_db
from app.kernel.models import User
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    token = credentials.credentials
    try:
        access_token = decode_access_token(token)
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效") from error
    context = get_kernel_context()
    if not token_is_active(context.capabilities.redis, access_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")
    user = db.get(User, access_token.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    settings = get_settings()
    skip_refresh = request.url.path.endswith(("/logout", "/password"))
    if response is not None and not skip_refresh and seconds_until(access_token.expires_at) <= settings.token_refresh_threshold_minutes * 60:
        renewed_token = create_access_token(user.id)
        whitelist_token(context.capabilities.redis, renewed_token)
        response.headers["Set-Token"] = renewed_token.value
    request.state.access_token = access_token
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
