"""FastAPI application entrypoint for the KeeperPilot backend."""

from fastapi import FastAPI

from backend.app.api.router import api_router
from backend.app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="KeeperPilot API",
    version="0.1.0",
    description="Autonomous DeFi operator - application layer on top of KeeperHub execution.",
    debug=settings.debug,
)

app.include_router(api_router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "keeperpilot-backend", "status": "ok"}
