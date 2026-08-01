"""Shared pytest fixtures."""

import os

os.environ.setdefault("KEEPERHUB_MOCK", "true")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
