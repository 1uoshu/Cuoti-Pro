from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any, Protocol

from fastapi import APIRouter

from app.kernel.context import KernelContext


class PluginFactory(Protocol):
    def __call__(self, context: KernelContext) -> "PluginSpec":
        ...


@dataclass(frozen=True)
class PluginSpec:
    name: str
    version: str
    description: str
    routers: tuple[APIRouter, ...] = ()
    dependencies: tuple[str, ...] = ()
    category: str = "feature"
    capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    tools: tuple[Any, ...] = ()  # tuple[ToolSpec, ...]，用 Any 避免循环导入


class PluginLoadError(RuntimeError):
    pass


class PluginManager:
    def __init__(self, specs: list[PluginSpec]):
        self._specs = specs

    @property
    def specs(self) -> list[PluginSpec]:
        return list(self._specs)

    def register_routers(self, api_router: APIRouter) -> None:
        for spec in self._specs:
            for router in spec.routers:
                api_router.include_router(router)

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "version": spec.version,
                "description": spec.description,
                "category": spec.category,
                "dependencies": list(spec.dependencies),
                "capabilities": list(spec.capabilities),
                "metadata": spec.metadata,
            }
            for spec in self._specs
        ]

    def collect_tools(self) -> list:
        """收集所有插件注册的工具"""
        from app.kernel.agent.tools import ToolSpec

        tools = []
        for spec in self._specs:
            for tool in spec.tools:
                if not isinstance(tool, ToolSpec):
                    raise PluginLoadError(
                        f"Plugin '{spec.name}' returned invalid ToolSpec"
                    )
                tools.append(tool)
        return tools


def load_plugins(module_names: list[str], context: KernelContext) -> PluginManager:
    specs = [_load_plugin(module_name, context) for module_name in module_names]
    return PluginManager(_sort_by_dependencies(specs))


def _load_plugin(module_name: str, context: KernelContext) -> PluginSpec:
    module = importlib.import_module(module_name)
    factory = getattr(module, "get_plugin", None)
    if factory is None:
        module = importlib.import_module(f"{module_name}.plugin")
        factory = getattr(module, "get_plugin", None)
    if factory is None:
        raise PluginLoadError(f"Plugin module {module_name} must expose get_plugin(context)")
    spec = factory(context)
    if not isinstance(spec, PluginSpec):
        raise PluginLoadError(f"Plugin module {module_name} returned an invalid PluginSpec")
    return spec


def _sort_by_dependencies(specs: list[PluginSpec]) -> list[PluginSpec]:
    by_name = {spec.name: spec for spec in specs}
    if len(by_name) != len(specs):
        raise PluginLoadError("Plugin names must be unique")

    ordered: list[PluginSpec] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise PluginLoadError(f"Plugin dependency cycle detected at {name}")
        spec = by_name.get(name)
        if spec is None:
            raise PluginLoadError(f"Plugin dependency {name} is not configured")
        visiting.add(name)
        for dependency in spec.dependencies:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        ordered.append(spec)

    for spec in specs:
        visit(spec.name)
    return ordered
