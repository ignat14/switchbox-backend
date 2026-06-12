from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.environments import connection as env_connection
from app.environments import service as env_service
from app.environments.schemas import (
    EnvironmentConnectionResponse,
    EnvironmentCreate,
    EnvironmentReorder,
    EnvironmentResponse,
    EnvironmentUpdate,
)
from app.middleware.auth import get_current_user
from app.projects.models import Project

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
    "/projects/{project_id}/environments/reorder",
    response_model=list[EnvironmentResponse],
)
async def reorder_environments(
    project_id: UUID,
    body: EnvironmentReorder,
    db: AsyncSession = Depends(get_db),
):
    return await env_service.reorder_environments(db, project_id, body)


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


@router.get(
    "/environments/{environment_id}/connection",
    response_model=EnvironmentConnectionResponse,
)
async def get_environment_connection(
    environment_id: UUID,
    user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    env = await env_service.get_environment(db, environment_id)
    # Ownership scoping (admin token sees everything). The rest of the API
    # gets this uniformly with SEC-1/REF-1; new endpoints start scoped.
    if user is not None:
        project = await db.get(Project, env.project_id)
        if project is None or project.user_id != user.id:
            raise HTTPException(status_code=404, detail="Environment not found")
    return await env_connection.get_connection(env)


@router.post(
    "/environments/{environment_id}/rotate-sdk-key",
    response_model=EnvironmentResponse,
)
async def rotate_sdk_key(
    environment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await env_service.rotate_sdk_key(db, environment_id)


@router.delete("/environments/{environment_id}", status_code=204)
async def delete_environment(
    environment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    await env_service.delete_environment(db, environment_id)
