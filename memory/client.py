"""The only module in this codebase allowed to talk to Supermemory directly.

Every other package (sim, agents, api, eval) must go through `SupermemoryClient`.
This keeps the memory schema (see schemas.py) enforced in one place and makes
the Phase 8 memory-on/off evaluation harness trustworthy -- "memory off" means
literally routing around this module.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from supermemory import Supermemory
from supermemory.types.document_get_response import DocumentGetResponse
from supermemory.types.document_list_response import DocumentListResponse
from supermemory.types.search_memories_params import Filters
from supermemory.types.search_memories_response import SearchMemoriesResponse
from supermemory.types.setting_get_response import SettingGetResponse

from .schemas import EventMemory, LessonMemory, MemoryRecord, RegimeSnapshotMemory, TradeMemory

SearchMode = Literal["memories", "hybrid", "documents"]

# Chunk-level embedding works without any extra config; the self-hosted
# "memory agent" (LLM fact extraction into consolidated memories) requires an
# LLM configured server-side. Default to hybrid so retrieval degrades
# gracefully to chunk search when that agent hasn't run -- see README.
DEFAULT_SEARCH_MODE: SearchMode = "hybrid"


def and_filters(**metadata_equals: str) -> Filters:
    """Build an AND-of-equals metadata filter, e.g. and_filters(strategy="momentum", regime="high_vol")."""
    return {
        "AND": [
            {"key": key, "value": str(value), "filterType": "metadata"}
            for key, value in metadata_equals.items()
        ]
    }


def or_filters(**metadata_equals: str) -> Filters:
    """Build an OR-of-equals metadata filter."""
    return {
        "OR": [
            {"key": key, "value": str(value), "filterType": "metadata"}
            for key, value in metadata_equals.items()
        ]
    }


class SupermemoryClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        container_tag: str | None = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("SUPERMEMORY_API_KEY")
        if not resolved_key:
            raise ValueError(
                "SUPERMEMORY_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        self.container_tag = container_tag or os.environ.get(
            "SUPERMEMORY_CONTAINER_TAG", "trading_system"
        )
        self._sdk = Supermemory(
            api_key=resolved_key,
            base_url=base_url or os.environ.get("SUPERMEMORY_BASE_URL", "http://localhost:6767"),
        )

    def _write(self, record: MemoryRecord) -> str:
        response = self._sdk.add(
            content=record.to_content(),
            container_tag=self.container_tag,
            metadata=record.to_metadata(),
        )
        return response.id

    def write_trade_memory(self, trade: TradeMemory) -> str:
        return self._write(trade)

    def write_lesson(self, lesson: LessonMemory) -> str:
        return self._write(lesson)

    def write_regime_snapshot(self, snapshot: RegimeSnapshotMemory) -> str:
        return self._write(snapshot)

    def write_event(self, event: EventMemory) -> str:
        return self._write(event)

    def query_similar(
        self,
        q: str,
        *,
        filters: Filters | None = None,
        limit: int = 10,
        search_mode: SearchMode = DEFAULT_SEARCH_MODE,
    ) -> SearchMemoriesResponse:
        kwargs: dict[str, Any] = {
            "q": q,
            "container_tag": self.container_tag,
            "limit": limit,
            "search_mode": search_mode,
        }
        if filters is not None:
            kwargs["filters"] = filters
        return self._sdk.search.memories(**kwargs)

    def get_user_profile(self, q: str | None = None):
        kwargs: dict[str, Any] = {"container_tag": self.container_tag}
        if q is not None:
            kwargs["q"] = q
        return self._sdk.profile(**kwargs)

    def configure_filter_prompt(self, filter_prompt: str) -> None:
        self._sdk.settings.update(filter_prompt=filter_prompt)

    def get_settings(self) -> SettingGetResponse:
        return self._sdk.settings.get()

    def document_status(self, document_id: str) -> str:
        return self._sdk.documents.get(id=document_id).status

    def list_documents(self, limit: int = 50, include_content: bool = True) -> DocumentListResponse:
        """List raw documents in this container -- id, status, metadata, and
        (if include_content) the stored text. Chunk-level embeddings themselves
        aren't exposed by the API (they're internal to the search engine); this
        is the practical observability surface for "what did we actually store."
        """
        return self._sdk.documents.list(
            container_tags=[self.container_tag],
            limit=limit,
            include_content=include_content,
        )

    def get_document(self, document_id: str) -> DocumentGetResponse:
        return self._sdk.documents.get(id=document_id)
