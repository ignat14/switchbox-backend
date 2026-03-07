from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flag import Flag
from app.schemas.flag import FlagCreate, FlagUpdate
from app.services.audit_service import log_action
from app.services.cdn_publisher import publish_flags


async def create_flag(db: AsyncSession, project_id: UUID, data: FlagCreate) -> Flag:
    flag = Flag(
        project_id=project_id,
        key=data.key,
        name=data.name,
        flag_type=data.flag_type,
        environment=data.environment,
        default_value=data.default_value,
    )
    db.add(flag)
    await db.commit()
    await db.refresh(flag)
    await log_action(db, flag.id, "created", new_value={"key": flag.key})
    await publish_flags(db, project_id, flag.environment)
    return flag


async def list_flags(
    db: AsyncSession, project_id: UUID, environment: str | None = None
) -> list[Flag]:
    stmt = select(Flag).where(Flag.project_id == project_id)
    if environment:
        stmt = stmt.where(Flag.environment == environment)
    stmt = stmt.order_by(Flag.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_flag(db: AsyncSession, flag_id: UUID) -> Flag:
    result = await db.execute(select(Flag).where(Flag.id == flag_id))
    flag = result.scalar_one_or_none()
    if flag is None:
        raise HTTPException(status_code=404, detail="Flag not found")
    return flag


async def update_flag(db: AsyncSession, flag_id: UUID, data: FlagUpdate) -> Flag:
    flag = await get_flag(db, flag_id)
    old = {"name": flag.name, "rollout_pct": flag.rollout_pct, "default_value": flag.default_value}
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(flag, field, value)
    await db.commit()
    await db.refresh(flag)
    new = {"name": flag.name, "rollout_pct": flag.rollout_pct, "default_value": flag.default_value}
    await log_action(db, flag_id, "updated", old_value=old, new_value=new)
    await publish_flags(db, flag.project_id, flag.environment)
    return flag


async def toggle_flag(db: AsyncSession, flag_id: UUID) -> Flag:
    flag = await get_flag(db, flag_id)
    old_enabled = flag.enabled
    flag.enabled = not flag.enabled
    await db.commit()
    await db.refresh(flag)
    await log_action(
        db, flag_id, "toggled", old_value={"enabled": old_enabled}, new_value={"enabled": flag.enabled}
    )
    await publish_flags(db, flag.project_id, flag.environment)
    return flag


async def delete_flag(db: AsyncSession, flag_id: UUID) -> None:
    flag = await get_flag(db, flag_id)
    project_id = flag.project_id
    environment = flag.environment
    await db.delete(flag)
    await db.commit()
    await publish_flags(db, project_id, environment)
