"""TROPEK API — FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="TROPEK API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}
