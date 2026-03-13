from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.environments.models import Environment
from app.flags.cdn_publisher import publish_flags
from app.middleware.auth import require_admin

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


@router.post("/publish/{project_id}/{environment_id}")
async def republish(
    project_id: UUID,
    environment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Environment).where(
            Environment.id == environment_id,
            Environment.project_id == project_id,
        )
    )
    env = result.scalar_one_or_none()
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    await publish_flags(db, project_id, environment_id, env.sdk_key)
    return {"status": "published"}
