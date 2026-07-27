"""Tool specification and registry for the Agent runtime."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class SideEffect(str, Enum):
    """工具副作用等级"""

    READ = "read"  # 不写库，可即跑
    WRITE = "write"  # 写库，一般可撤回
    SEND = "send"  # 外发，永远要红字确认


@dataclass(frozen=True)
class ToolSpec:
    """工具元数据信封，内核强制，插件只能填值不能绕过"""

    name: str  # 格式: Plugin::Tool (PascalCase + ::)
    description: str  # 工具描述
    short_intent: str  # 6-18 个汉字，Plan Panel 折叠态显示
    side_effect: SideEffect  # 副作用等级
    requires_confirmation: bool  # side_effect=SEND 时必须为 True
    handler: Callable[..., Any]  # 实际执行函数（async callable）
    preconditions: tuple[str, ...] = ()  # 前置条件描述
    autonomous: bool = False  # True=Agent自主发起, False=学生显式选择
    schema: dict[str, Any] | None = None  # JSON Schema for args

    def __post_init__(self):
        if self.side_effect == SideEffect.SEND and not self.requires_confirmation:
            raise ValueError(
                f"Tool '{self.name}' has side_effect=SEND but requires_confirmation=False"
            )


class ToolRegistry:
    """内核拥有的工具注册表，收集所有插件注册的工具"""

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        if tool.name in self._tools:
            return  # 幂等：已注册则跳过（测试环境 lifespan 可能多次执行）
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_all(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def list_by_side_effect(self, side_effect: SideEffect) -> list[ToolSpec]:
        return [t for t in self._tools.values() if t.side_effect == side_effect]

    def describe_all(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "short_intent": t.short_intent,
                "side_effect": t.side_effect.value,
                "requires_confirmation": t.requires_confirmation,
                "autonomous": t.autonomous,
                "preconditions": list(t.preconditions),
            }
            for t in self._tools.values()
        ]
