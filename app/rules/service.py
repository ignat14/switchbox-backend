from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import log_action
from app.flags.cdn_publisher import publish_flags
from app.flags.service import get_flag
from app.rules.models import Rule
from app.rules.schemas import RuleCreate


async def add_rule(
    db: AsyncSession, flag_id: UUID, data: RuleCreate, changed_by: str | None = None
) -> Rule:
    flag = await get_flag(db, flag_id)
    rule = Rule(
        flag_id=flag_id,
        attribute=data.attribute,
        operator=data.operator,
        value=data.value,
    )
    db.add(rule)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(rule)
    await log_action(
        db, flag_id, "rule_added",
        new_value={"attribute": rule.attribute, "operator": rule.operator},
        changed_by=changed_by,
    )
    await publish_flags(db, flag.project_id, flag.environment)
    return rule


async def remove_rule(db: AsyncSession, rule_id: UUID, changed_by: str | None = None) -> None:
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    flag = await get_flag(db, rule.flag_id)
    await db.delete(rule)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await log_action(
        db, flag.id, "rule_removed",
        old_value={"attribute": rule.attribute, "operator": rule.operator},
        changed_by=changed_by,
    )
    await publish_flags(db, flag.project_id, flag.environment)
