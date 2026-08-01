"""Execution routes (authenticated, user-scoped)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.schemas.executions import ExecutionRequest, ExecutionResponse
from backend.app.services import executions as executions_service
from backend.app.services.executions import (
    ExecutionConflictError,
    ExecutionError,
    ExecutionNotFoundError,
)
from database.models import User
from database.session import get_db

router = APIRouter(prefix="/executions", tags=["executions"])

db_dep = Annotated[AsyncSession, Depends(get_db)]
current_user_dep = Annotated[User, Depends(get_current_user)]


def _parse_id(wallet_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(wallet_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc


def _map_error(exc: ExecutionError, *, not_found: bool = False) -> HTTPException:
    if isinstance(exc, ExecutionNotFoundError) or not_found:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ExecutionConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=ExecutionResponse, status_code=201)
async def create_execution(
    payload: ExecutionRequest,
    db: db_dep,
    user: current_user_dep,
) -> ExecutionResponse:
    """Create a pending execution. The move is re-verified against policy."""
    try:
        execution = await executions_service.create_execution(db, user, payload)
    except ExecutionNotFoundError as exc:
        raise _map_error(exc) from exc
    except ExecutionConflictError as exc:
        raise _map_error(exc) from exc
    except ExecutionError as exc:
        raise _map_error(exc) from exc
    return ExecutionResponse.model_validate(execution)


@router.get("", response_model=list[ExecutionResponse])
async def list_executions(db: db_dep, user: current_user_dep) -> list[ExecutionResponse]:
    executions = await executions_service.list_executions(db, user)
    return [ExecutionResponse.model_validate(e) for e in executions]


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: str, db: db_dep, user: current_user_dep
) -> ExecutionResponse:
    parsed = _parse_id(execution_id)
    try:
        execution = await executions_service.get_execution(db, user, parsed)
    except ExecutionNotFoundError as exc:
        raise _map_error(exc) from exc
    return ExecutionResponse.model_validate(execution)


@router.post("/{execution_id}/approve", response_model=ExecutionResponse)
async def approve_execution(
    execution_id: str, db: db_dep, user: current_user_dep
) -> ExecutionResponse:
    """Approve a pending execution and submit it through the execution layer."""
    parsed = _parse_id(execution_id)
    try:
        execution = await executions_service.approve_execution(db, user, parsed)
    except ExecutionNotFoundError as exc:
        raise _map_error(exc) from exc
    except ExecutionError as exc:
        raise _map_error(exc) from exc
    return ExecutionResponse.model_validate(execution)


@router.post("/{execution_id}/reject", response_model=ExecutionResponse)
async def reject_execution(
    execution_id: str, db: db_dep, user: current_user_dep
) -> ExecutionResponse:
    parsed = _parse_id(execution_id)
    try:
        execution = await executions_service.reject_execution(db, user, parsed)
    except ExecutionNotFoundError as exc:
        raise _map_error(exc) from exc
    except ExecutionError as exc:
        raise _map_error(exc) from exc
    return ExecutionResponse.model_validate(execution)


@router.post("/{execution_id}/cancel", response_model=ExecutionResponse)
async def cancel_execution(
    execution_id: str, db: db_dep, user: current_user_dep
) -> ExecutionResponse:
    parsed = _parse_id(execution_id)
    try:
        execution = await executions_service.cancel_execution(db, user, parsed)
    except ExecutionNotFoundError as exc:
        raise _map_error(exc) from exc
    except ExecutionError as exc:
        raise _map_error(exc) from exc
    return ExecutionResponse.model_validate(execution)


@router.post("/{execution_id}/refresh", response_model=ExecutionResponse)
async def refresh_execution(
    execution_id: str, db: db_dep, user: current_user_dep
) -> ExecutionResponse:
    """Poll the execution layer for the latest on-chain status."""
    parsed = _parse_id(execution_id)
    try:
        execution = await executions_service.refresh_execution(db, user, parsed)
    except ExecutionNotFoundError as exc:
        raise _map_error(exc) from exc
    except ExecutionError as exc:
        raise _map_error(exc) from exc
    return ExecutionResponse.model_validate(execution)
