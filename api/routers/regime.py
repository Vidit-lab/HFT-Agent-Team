from fastapi import APIRouter, Depends, Query

from api.deps import get_memory_client
from api.schemas import RegimeOut, RegimeSnapshotOut
from memory.client import SupermemoryClient, and_filters

router = APIRouter(prefix="/api/regime", tags=["regime"])


@router.get("", response_model=RegimeOut)
def get_regime(
    q: str = Query("current market regime", description="Semantic search query"),
    asset: str | None = None,
    limit: int = Query(5, ge=1, le=50),
    client: SupermemoryClient = Depends(get_memory_client),
):
    filter_fields = {"type": "regime_snapshot"}
    if asset:
        filter_fields["asset"] = asset

    results = client.query_similar(q, filters=and_filters(**filter_fields), limit=limit)
    snapshots = [
        RegimeSnapshotOut(
            asset=r.metadata.get("asset"),
            regime=r.metadata.get("regime"),
            summary=r.chunk,
            similarity=r.similarity,
        )
        for r in results.results
    ]
    return RegimeOut(query=q, snapshots=snapshots)
