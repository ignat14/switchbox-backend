from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def log_action(
    db: AsyncSession,
    flag_id: UUID,
    action: str,
    old_value: Any = None,
    new_value: Any = None,
    changed_by: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        flag_id=flag_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        changed_by=changed_by,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def get_flag_audit(db: AsyncSession, flag_id: UUID) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.flag_id == flag_id)
        .order_by(AuditLog.timestamp.desc())
    )
    return list(result.scalars().all())
