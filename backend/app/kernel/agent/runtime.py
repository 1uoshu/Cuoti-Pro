from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph


@dataclass(frozen=True)
class AgentStep:
    name: str
    handler: Callable[[Any], Any]


class AgentRuntime:
    """Kernel-owned LangGraph helper used by plugins to build workflows."""

    def compile_linear_workflow(self, state_schema: type, steps: list[AgentStep]):
        if not steps:
            raise ValueError("Agent workflow must contain at least one step")
        graph = StateGraph(state_schema)
        for step in steps:
            graph.add_node(step.name, step.handler)
        graph.add_edge(START, steps[0].name)
        for current, next_step in zip(steps, steps[1:]):
            graph.add_edge(current.name, next_step.name)
        graph.add_edge(steps[-1].name, END)
        return graph.compile()
