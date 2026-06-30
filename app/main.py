from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.wecom_callback import router as wecom_callback_router
from app.config import settings
from app.scheduler import start_scheduler, stop_scheduler


logging.basicConfig(
    level=getattr(logging, settings.app_log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="stock-analyze", lifespan=lifespan)
app.include_router(wecom_callback_router)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "symbol": settings.app_symbol,
        "pollingEnabled": settings.app_polling_enabled,
        "callbackPath": settings.wecom_callback_path,
    }
