"""FastAPI application entrypoint for the KeeperPilot backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="KeeperPilot API",
    version="0.1.0",
    description="Autonomous DeFi operator - application layer on top of KeeperHub execution.",
    debug=settings.debug,
)

# The Next.js frontend runs on its own origin (http://localhost:3000 in dev).
# CORS is scoped to configured origins so the browser can call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "keeperpilot-backend", "status": "ok"}
