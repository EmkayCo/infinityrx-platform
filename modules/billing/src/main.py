"""Billing module FastAPI application entry point."""

from fastapi import FastAPI
from src.api.router import router

app = FastAPI(
    title="InfinityRx Billing",
    version="1.0.0",
    description="Billing module — claims, AP, AR, invoicing, journal, program monitoring",
)

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "module": "billing"}
