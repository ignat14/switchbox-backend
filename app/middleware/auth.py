import secrets
import uuid

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import verify_token
from app.config import settings
from app.database import get_db
from app.projects.models import Project
from app.projects.service import get_project_by_api_key


async def require_admin(authorization: str = Header()) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.removeprefix("Bearer ")
    if not settings.ADMIN_TOKEN or not secrets.compare_digest(token, settings.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return token


async def get_current_user(
    authorization: str = Header(), db: AsyncSession = Depends(get_db)
) -> User | None:
    """Authenticate via admin token (returns None) or JWT (returns User)."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.removeprefix("Bearer ")

    # Admin token → superadmin, no user object
    if settings.ADMIN_TOKEN and secrets.compare_digest(token, settings.ADMIN_TOKEN):
        return None

    # JWT → resolve user
    try:
        payload = verify_token(token)
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_api_key(
    x_api_key: str = Header(), db: AsyncSession = Depends(get_db)
) -> Project:
    project = await get_project_by_api_key(db, x_api_key)
    if project is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return project
