from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.environments import service as env_service
from app.environments.schemas import (
    EnvironmentCreate,
    EnvironmentResponse,
    EnvironmentUpdate,
)
from app.middleware.auth import get_current_user

router = APIRouter(tags=["environments"], dependencies=[Depends(get_current_user)])


@router.get(
    "/projects/{project_id}/environments",
    response_model=list[EnvironmentResponse],
)
async def list_environments(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await env_service.list_environments(db, project_id)


@router.post(
    "/projects/{project_id}/environments",
    response_model=EnvironmentResponse,
    status_code=201,
)
async def create_environment(
    project_id: UUID,
    body: EnvironmentCreate,
    db: AsyncSession = Depends(get_db),
):
    return await env_service.create_environment(db, project_id, body)


@router.patch(
    "/environments/{environment_id}",
    response_model=EnvironmentResponse,
)
async def update_environment(
    environment_id: UUID,
    body: EnvironmentUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await env_service.update_environment(db, environment_id, body)


@router.delete("/environments/{environment_id}", status_code=204)
async def delete_environment(
    environment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await env_service.delete_environment(db, environment_id)
