from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from api.routers import backtest, consolidate, cycle, demo, lessons, market, memory, portfolio, reflect, regime, trades  # noqa: E402 -- must follow load_dotenv()

app = FastAPI(title="AlphaMemoir API", version="0.1.0")

# The Vite dev server proxies /api, but allow direct cross-origin calls too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router)
app.include_router(trades.router)
app.include_router(regime.router)
app.include_router(lessons.router)
app.include_router(cycle.router)
app.include_router(backtest.router)
app.include_router(reflect.router)
app.include_router(consolidate.router)
app.include_router(memory.router)
app.include_router(market.router)
app.include_router(demo.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


# ── Serve the built SPA from the same origin, if it has been built ────────────
#
# One process, one port, one thing to deploy. In development this directory
# doesn't exist and the block is skipped entirely -- Vite serves the frontend on
# :5173 and proxies /api here, which is what the CORS rule above is for.
_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """Hand every non-API path back to index.html.

        The router is client-side, so a hard refresh on /memory or a pasted deep
        link must not 404 -- the browser has to receive the app and let React
        Router resolve the route.
        """
        asset = _DIST / full_path
        if full_path and asset.is_file():
            return FileResponse(asset)
        return FileResponse(_DIST / "index.html")
