from typing import Any


def ok(data: Any) -> dict[str, Any]:
    return {"code": 0, "message": "success", "data": data}


def error(code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data}
