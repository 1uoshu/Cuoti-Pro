from __future__ import annotations

from app.kernel.auth.security import AccessToken, seconds_until, token_fingerprint
from app.kernel.redis import RedisStore

_TOKEN_PREFIX = "auth:token:"
_USER_TOKENS_PREFIX = "auth:user:tokens:"


def whitelist_token(redis: RedisStore, token: AccessToken) -> None:
    ttl = seconds_until(token.expires_at)
    fingerprint = token_fingerprint(token.value)
    redis.set(_token_key(fingerprint), str(token.user_id), ex=ttl)
    user_tokens_key = _user_tokens_key(token.user_id)
    redis.sadd(user_tokens_key, fingerprint)
    redis.expire(user_tokens_key, ttl)


def token_is_active(redis: RedisStore, token: AccessToken) -> bool:
    return redis.get(_token_key(token_fingerprint(token.value))) == str(token.user_id)


def revoke_token(redis: RedisStore, token: AccessToken) -> None:
    fingerprint = token_fingerprint(token.value)
    redis.delete(_token_key(fingerprint))


def revoke_all_user_tokens(redis: RedisStore, user_id: int) -> None:
    user_tokens_key = _user_tokens_key(user_id)
    fingerprints = redis.smembers(user_tokens_key)
    if fingerprints:
        redis.delete(*(_token_key(fingerprint) for fingerprint in fingerprints))
    redis.delete(user_tokens_key)


def _token_key(fingerprint: str) -> str:
    return f"{_TOKEN_PREFIX}{fingerprint}"


def _user_tokens_key(user_id: int) -> str:
    return f"{_USER_TOKENS_PREFIX}{user_id}"
