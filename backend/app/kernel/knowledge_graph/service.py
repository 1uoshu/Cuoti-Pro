from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class KnowledgeGraphNode:
    id: str
    label: str
    kind: str = "knowledge_point"
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeGraphEdge:
    source: str
    target: str
    relation: str
    weight: float = 1
    properties: dict[str, Any] = field(default_factory=dict)


class KnowledgeGraphService:
    """Kernel seam for the future graph database adapter."""

    async def upsert_node(self, node: KnowledgeGraphNode) -> KnowledgeGraphNode:
        return node

    async def link(self, edge: KnowledgeGraphEdge) -> KnowledgeGraphEdge:
        return edge

    async def neighbors(self, node_id: str, *, relation: str | None = None) -> list[KnowledgeGraphNode]:
        _ = (node_id, relation)
        return []
