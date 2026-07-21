from typing import Any


def normalize_question_grade(payload: dict[str, Any], *, default_confidence: float = 1) -> dict[str, Any]:
    is_correct = _as_bool(first(payload, "is_correct", "correct"), "is_correct")
    score = as_float(first(payload, "score", default=10 if is_correct else 0), "score")
    max_score = as_float(first(payload, "max_score", "full_score", default=max(10, score)), "max_score")
    if score < 0 or max_score <= 0 or score > max_score:
        raise ValueError("Agent grade score is outside the valid range")
    confidence = as_float(first(payload, "confidence", default=default_confidence), "confidence")
    if not 0 <= confidence <= 1:
        raise ValueError("Agent grade confidence is outside the valid range")
    return {
        "is_correct": is_correct,
        "score": score,
        "max_score": max_score,
        "explanation": required_text(payload, "explanation", "feedback", "reason", "analysis"),
        "confidence": confidence,
    }


def first(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def required_text(mapping: dict[str, Any], *keys: str) -> str:
    value = optional_text(mapping, *keys)
    if not value:
        raise ValueError(f"Agent response is missing text field: {', '.join(keys)}")
    return value


def optional_text(mapping: dict[str, Any], *keys: str) -> str | None:
    value = first(mapping, *keys)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_float(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"Agent response field {field} must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Agent response field {field} must be numeric") from error


def _as_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValueError(f"Agent response field {field} must be a boolean")
