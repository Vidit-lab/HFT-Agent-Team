"""POST /api/run-cycle -- an honest stub.

Unlike /api/backtest, this genuinely can't be implemented yet: it requires
the agent orchestrator (Phase 4), which doesn't exist. Returns 501 with a
clear explanation rather than faking a 200.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/run-cycle", tags=["cycle"])


@router.post("")
def run_cycle():
    raise HTTPException(
        status_code=501,
        detail=(
            "run-cycle requires the agent orchestrator, which doesn't exist yet "
            "(Phase 4). Use POST /api/backtest to exercise the deterministic "
            "engine in the meantime."
        ),
    )
