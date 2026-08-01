"""Aggregate API router."""

from fastapi import APIRouter

from backend.app.api.routes import auth, health, preferences, wallets

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(wallets.router, tags=["wallets"])
api_router.include_router(preferences.router, tags=["preferences"])
