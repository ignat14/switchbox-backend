from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.environments.service import create_default_environments
from app.flags.models import Flag
from app.projects.models import Project


async def create_project(
    db: AsyncSession, name: str, user_id: UUID | None = None
) -> Project:
    project = Project(name=name, user_id=user_id)
    db.add(project)
    await db.flush()
    await create_default_environments(db, project.id)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(project)
    return project


async def list_projects(
    db: AsyncSession, user_id: UUID | None = None
) -> list[Project]:
    flag_count = (
        select(func.count(Flag.id))
        .where(Flag.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    stmt = select(Project, flag_count)
    if user_id is not None:
        stmt = stmt.where(Project.user_id == user_id)
    stmt = stmt.order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    projects = []
    for project, count in result.all():
        project.flag_count = count
        projects.append(project)
    return projects


async def get_project(db: AsyncSession, project_id: UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project.flag_count = await db.scalar(
        select(func.count(Flag.id)).where(Flag.project_id == project_id)
    )
    return project
