from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from api.routers import backtest, cycle, lessons, portfolio, regime, trades  # noqa: E402 -- must follow load_dotenv()

app = FastAPI(title="Trading Brain API", version="0.1.0")

app.include_router(portfolio.router)
app.include_router(trades.router)
app.include_router(regime.router)
app.include_router(lessons.router)
app.include_router(cycle.router)
app.include_router(backtest.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
