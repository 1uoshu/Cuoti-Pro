from typing import Any


GENERIC_SERVER_ERROR_MESSAGE = "服务器处理请求时发生错误"
SAFE_AGENT_ERROR_MESSAGE = "智能服务暂时不可用，请稍后重试"
SAFE_UPLOAD_ERROR_MESSAGE = "文件暂时无法保存，请稍后重试"


def ok(data: Any) -> dict[str, Any]:
    return {"code": 0, "message": "success", "data": data}


def error(code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data}
