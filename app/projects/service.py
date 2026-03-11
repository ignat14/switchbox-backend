import hashlib
import secrets
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.projects.models import Project


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


async def create_project(
    db: AsyncSession, name: str, user_id: UUID | None = None
) -> tuple[Project, str]:
    api_key = secrets.token_urlsafe(32)
    project = Project(name=name, api_key_hash=_hash_key(api_key), user_id=user_id)
    db.add(project)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(project)
    return project, api_key


async def list_projects(
    db: AsyncSession, user_id: UUID | None = None
) -> list[Project]:
    stmt = select(Project)
    if user_id is not None:
        stmt = stmt.where(Project.user_id == user_id)
    stmt = stmt.order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_project_by_api_key(
    db: AsyncSession, plaintext_key: str
) -> Project | None:
    key_hash = _hash_key(plaintext_key)
    result = await db.execute(
        select(Project).where(Project.api_key_hash == key_hash)
    )
    return result.scalar_one_or_none()


async def rotate_api_key(db: AsyncSession, project_id: UUID) -> tuple[Project, str]:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    api_key = secrets.token_urlsafe(32)
    project.api_key_hash = _hash_key(api_key)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(project)
    return project, api_key
