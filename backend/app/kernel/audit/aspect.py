"""审计切面 -- 自动为路由添加审计记录。
写操作审计失败时，业务事务回滚。
"""
from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable

from fastapi import Request
from sqlalchemy.orm import Session

from app.kernel.context import get_kernel_context
from app.kernel.models import User


def audited(
    event_type: str,
    resource_type: str,
    *,
    summary_template: str = "",
    extract_resource_id: Callable[..., Any] | None = None,
):
    """路由审计装饰器。

    Args:
        event_type: 审计事件类型（如 "assignment.uploaded"）
        resource_type: 资源类型（如 "assignment"）
        summary_template: 摘要模板（支持 {resource_id} 等占位符）
        extract_resource_id: 从路由返回值提取 resource_id 的函数
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 提取 request 和 user
            request: Request | None = kwargs.get("request")
            user: User | None = kwargs.get("user")
            db: Session | None = kwargs.get("db")

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
            except Exception:
                # 业务失败也要审计
                if db and user:
                    context = get_kernel_context()
                    context.capabilities.audit.record(
                        db,
                        event_type=f"{event_type}.failed",
                        actor=user,
                        outcome="failure",
                        resource_type=resource_type,
                        summary=f"{summary_template} 失败" if summary_template else f"{event_type} 失败",
                        request=request,
                        commit=True,
                    )
                raise

            # 业务成功 -> 审计
            if db and user:
                resource_id = None
                if extract_resource_id:
                    try:
                        resource_id = extract_resource_id(result)
                    except Exception:
                        pass
                context = get_kernel_context()
                context.capabilities.audit.record(
                    db,
                    event_type=event_type,
                    actor=user,
                    outcome="success",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    summary=summary_template.format(resource_id=resource_id) if summary_template else event_type,
                    request=request,
                    commit=True,
                )
            return result

        return wrapper

    return decorator
