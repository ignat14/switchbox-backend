from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.middleware.auth import get_current_user
from app.projects import service as project_service
from app.projects.schemas import (
    ApiKeyRotateResponse,
    ProjectCreate,
    ProjectCreateResponse,
    ProjectResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(get_current_user)])


@router.post("", response_model=ProjectCreateResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    project, api_key = await project_service.create_project(
        db, body.name, user_id=user.id if user else None
    )
    return ProjectCreateResponse(
        id=project.id,
        name=project.name,
        created_at=project.created_at,
        api_key=api_key,
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return await project_service.list_projects(db, user_id=user.id if user else None)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await project_service.get_project(db, project_id)


@router.post("/{project_id}/rotate-key", response_model=ApiKeyRotateResponse)
async def rotate_key(project_id: UUID, db: AsyncSession = Depends(get_db)):
    _, api_key = await project_service.rotate_api_key(db, project_id)
    return ApiKeyRotateResponse(api_key=api_key)
