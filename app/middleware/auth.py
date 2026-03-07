import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.project import Project
from app.services.project_service import get_project_by_api_key


async def require_admin(authorization: str = Header()) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.removeprefix("Bearer ")
    if not settings.ADMIN_TOKEN or not secrets.compare_digest(token, settings.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return token


async def require_api_key(
    x_api_key: str = Header(), db: AsyncSession = Depends(get_db)
) -> Project:
    project = await get_project_by_api_key(db, x_api_key)
    if project is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return project
