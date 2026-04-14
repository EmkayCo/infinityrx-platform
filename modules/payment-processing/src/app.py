"""Payment-processing FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI

from .api.router import router
from .events import consumers as _consumers  # noqa: F401 — registers handlers

app = FastAPI(
    title="InfinityRx Payment Processing",
    version="1.0.0",
    description="Payment vendor adapter layer: NACHA, Echo, Zelis, Check issuance",
)

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "module": "payment-processing"}
