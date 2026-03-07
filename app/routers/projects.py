from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_admin
from app.schemas.project import (
    ApiKeyRotateResponse,
    ProjectCreate,
    ProjectCreateResponse,
    ProjectResponse,
)
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(require_admin)])


@router.post("", response_model=ProjectCreateResponse, status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project, api_key = await project_service.create_project(db, body.name)
    return ProjectCreateResponse(
        id=project.id,
        name=project.name,
        created_at=project.created_at,
        api_key=api_key,
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    return await project_service.list_projects(db)


@router.post("/{project_id}/rotate-key", response_model=ApiKeyRotateResponse)
async def rotate_key(project_id: UUID, db: AsyncSession = Depends(get_db)):
    _, api_key = await project_service.rotate_api_key(db, project_id)
    return ApiKeyRotateResponse(api_key=api_key)
