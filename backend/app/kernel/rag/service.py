from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RAGDocument:
    id: str
    text: str
    score: float = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class RAGService:
    """Kernel seam for future vector retrieval and reranking."""

    async def retrieve(self, query: str, *, top_k: int = 5, filters: dict[str, Any] | None = None) -> list[RAGDocument]:
        _ = (query, top_k, filters)
        return []
