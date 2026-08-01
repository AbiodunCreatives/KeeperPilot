"""Health check endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.core.config import Settings, get_settings

router = APIRouter()

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/health")
async def health(settings: SettingsDep) -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "keeperhub_mock": str(settings.keeperhub_mock).lower(),
    }
