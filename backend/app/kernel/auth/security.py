from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import secrets

import jwt
from pwdlib import PasswordHash

from app.kernel.config import get_settings


password_hash = PasswordHash.recommended()


@dataclass(frozen=True)
class AccessToken:
    value: str
    user_id: int
    jti: str
    expires_at: datetime


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: int) -> AccessToken:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(hours=settings.jwt_expire_hours)
    jti = secrets.token_urlsafe(24)
    value = jwt.encode(
        {"sub": str(user_id), "exp": expires_at, "jti": jti, "typ": "access"},
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    return AccessToken(value=value, user_id=user_id, jti=jti, expires_at=expires_at)


def decode_access_token(token: str) -> AccessToken:
    payload = jwt.decode(token, get_settings().jwt_secret_key, algorithms=["HS256"])
    expires_at = datetime.fromtimestamp(float(payload["exp"]), tz=UTC)
    if payload.get("typ") != "access":
        raise ValueError("invalid token type")
    return AccessToken(
        value=token,
        user_id=int(payload["sub"]),
        jti=str(payload["jti"]),
        expires_at=expires_at,
    )


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def seconds_until(expires_at: datetime) -> int:
    return max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
