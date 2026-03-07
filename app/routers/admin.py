from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_admin
from app.services.cdn_publisher import publish_flags

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/publish/{project_id}/{environment}")
async def republish(
    project_id: UUID, environment: str, db: AsyncSession = Depends(get_db)
):
    await publish_flags(db, project_id, environment)
    return {"status": "published"}
