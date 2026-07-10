from fastapi import APIRouter, Depends, Query

from api.deps import get_memory_client
from api.schemas import LessonOut, LessonsOut
from memory.client import SupermemoryClient, and_filters

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("", response_model=LessonsOut)
def get_lessons(
    q: str = Query("trading lessons", description="Semantic search query"),
    strategy: str | None = None,
    regime: str | None = None,
    limit: int = Query(10, ge=1, le=50),
    client: SupermemoryClient = Depends(get_memory_client),
):
    filter_fields = {"type": "lesson"}
    if strategy:
        filter_fields["strategy"] = strategy
    if regime:
        filter_fields["regime"] = regime

    results = client.query_similar(q, filters=and_filters(**filter_fields), limit=limit)
    lessons = [
        LessonOut(
            lesson_text=r.chunk,
            strategy=r.metadata.get("strategy"),
            regime=r.metadata.get("regime"),
            asset=r.metadata.get("asset"),
            outcome=r.metadata.get("outcome"),
            similarity=r.similarity,
        )
        for r in results.results
    ]
    return LessonsOut(query=q, lessons=lessons)
