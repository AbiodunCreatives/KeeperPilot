"""Authentication routes: register (email) -> JWT access token."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import create_access_token
from backend.app.schemas.auth import RegisterRequest, TokenResponse, UserResponse
from database.models import AuditLog, User
from database.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

db_dep = Annotated[AsyncSession, Depends(get_db)]


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, db: db_dep) -> TokenResponse:
    """Create an account or return a fresh token for an existing email."""
    stmt = select(User).where(User.email == payload.email.lower())
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None:
        user = User(email=payload.email.lower())
        db.add(user)
        await db.flush()
        db.add(
            AuditLog(
                event="auth.user_registered",
                description=f"New account for {user.email}",
                user_id=user.id,
            )
        )
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))
