from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.kernel.config import Settings
from app.kernel.models import SystemSetting

SECRET_FIELDS = {"openai_api_key"}
MANAGED_FIELDS = {
    "openai_api_key",
    "openai_base_url",
    "openai_model",
    "openai_reasoning_effort",
    "openai_disable_response_storage",
    "openai_timeout_seconds",
    "max_upload_mb",
    "max_pdf_pages",
    "review_confidence_threshold",
    "token_refresh_threshold_minutes",
    "pow_challenge_ttl_seconds",
    "pow_difficulty",
}


def load_runtime_settings(db: Session, settings: Settings) -> None:
    for record in db.query(SystemSetting).all():
        if record.key not in MANAGED_FIELDS:
            continue
        value = _decode_value(record, settings)
        setattr(settings, record.key, value)


def update_runtime_settings(db: Session, settings: Settings, updates: dict[str, Any]) -> list[str]:
    changed_fields: list[str] = []
    for key, value in updates.items():
        if key not in MANAGED_FIELDS:
            continue
        stored_value = _encode_value(value, key in SECRET_FIELDS, settings)
        record = db.get(SystemSetting, key)
        if record is None:
            record = SystemSetting(key=key, value=stored_value, is_secret=key in SECRET_FIELDS)
            db.add(record)
        else:
            record.value = stored_value
            record.is_secret = key in SECRET_FIELDS
        setattr(settings, key, value)
        changed_fields.append(key)
    return changed_fields


def serialize_runtime_settings(settings: Settings) -> dict[str, Any]:
    result = {key: getattr(settings, key) for key in MANAGED_FIELDS - SECRET_FIELDS}
    result["openai_api_key_configured"] = bool(settings.openai_api_key)
    return result


def _encode_value(value: Any, is_secret: bool, settings: Settings) -> str:
    raw_value = json.dumps(value)
    return _fernet(settings).encrypt(raw_value.encode()).decode() if is_secret else raw_value


def _decode_value(record: SystemSetting, settings: Settings) -> Any:
    raw_value = _fernet(settings).decrypt(record.value.encode()).decode() if record.is_secret else record.value
    return json.loads(raw_value)


def _fernet(settings: Settings) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret_key.encode()).digest())
    return Fernet(key)
