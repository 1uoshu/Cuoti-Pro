from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import secrets
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException, Request, status

from app.kernel.config import Settings
from app.kernel.redis import RedisStore

PowPurpose = Literal["login", "register"]
_POW_PREFIX = "auth:pow:"


def create_challenge(redis: RedisStore, settings: Settings, request: Request, purpose: PowPurpose) -> dict[str, object]:
    challenge_id = uuid4().hex
    nonce_seed = secrets.token_urlsafe(24)
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.pow_challenge_ttl_seconds)
    record = {
        "purpose": purpose,
        "ip": _client_ip(request),
        "user_agent": request.headers.get("user-agent", ""),
        "nonce_seed": nonce_seed,
        "difficulty": settings.pow_difficulty,
        "expires_at": expires_at.isoformat(),
    }
    redis.set(_key(challenge_id), json.dumps(record), ex=settings.pow_challenge_ttl_seconds)
    return {"challenge_id": challenge_id, "purpose": purpose, "difficulty": settings.pow_difficulty, "nonce_seed": nonce_seed, "expires_at": expires_at.isoformat()}


def verify_and_consume_challenge(
    redis: RedisStore,
    request: Request,
    *,
    purpose: PowPurpose,
    challenge_id: str,
    nonce: str,
) -> None:
    serialized = redis.getdel(_key(challenge_id))
    if serialized is None:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="PoW challenge 已过期或已使用")
    try:
        record = json.loads(serialized)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PoW challenge 无效") from error
    if record.get("purpose") != purpose:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PoW challenge 用途不匹配")
    if record.get("ip") != _client_ip(request) or record.get("user_agent") != request.headers.get("user-agent", ""):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PoW challenge 客户端上下文不匹配")
    difficulty = record.get("difficulty")
    nonce_seed = record.get("nonce_seed")
    if not isinstance(difficulty, int) or not isinstance(nonce_seed, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PoW challenge 无效")
    digest = hashlib.sha256(f"{nonce_seed}:{nonce}".encode("utf-8")).hexdigest()
    if not digest.startswith("0" * difficulty):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PoW 校验失败")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _key(challenge_id: str) -> str:
    return f"{_POW_PREFIX}{challenge_id}"
