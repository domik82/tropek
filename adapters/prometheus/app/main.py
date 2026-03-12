"""TROPEK Prometheus adapter — FastAPI entry point."""

from fastapi import FastAPI

app = FastAPI(title="TROPEK Prometheus Adapter", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """Return adapter health status and datasource identifier."""
    return {"status": "ok", "datasource": "prometheus"}
