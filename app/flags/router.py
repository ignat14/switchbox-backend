from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service
from app.auth.models import User
from app.database import get_db
from app.flags import service as flag_service
from app.flags.schemas import FlagCreate, FlagResponse, FlagUpdate
from app.audit.schemas import AuditLogResponse
from app.middleware.auth import get_current_user

router = APIRouter(tags=["flags"], dependencies=[Depends(get_current_user)])


def _actor(user: User | None) -> str | None:
    return user.github_login if user else "admin"


@router.post(
    "/projects/{project_id}/flags", response_model=FlagResponse, status_code=201
)
async def create_flag(
    project_id: UUID,
    body: FlagCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return await flag_service.create_flag(db, project_id, body, changed_by=_actor(user))


@router.get("/projects/{project_id}/flags", response_model=list[FlagResponse])
async def list_flags(
    project_id: UUID,
    environment: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await flag_service.list_flags(db, project_id, environment)


@router.get("/flags/{flag_id}", response_model=FlagResponse)
async def get_flag(flag_id: UUID, db: AsyncSession = Depends(get_db)):
    return await flag_service.get_flag(db, flag_id)


@router.patch("/flags/{flag_id}", response_model=FlagResponse)
async def update_flag(
    flag_id: UUID,
    body: FlagUpdate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return await flag_service.update_flag(db, flag_id, body, changed_by=_actor(user))


@router.post("/flags/{flag_id}/toggle", response_model=FlagResponse)
async def toggle_flag(
    flag_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    return await flag_service.toggle_flag(db, flag_id, changed_by=_actor(user))


@router.delete("/flags/{flag_id}", status_code=204)
async def delete_flag(flag_id: UUID, db: AsyncSession = Depends(get_db)):
    await flag_service.delete_flag(db, flag_id)


@router.get("/flags/{flag_id}/audit", response_model=list[AuditLogResponse])
async def get_flag_audit(flag_id: UUID, db: AsyncSession = Depends(get_db)):
    return await audit_service.get_flag_audit(db, flag_id)
