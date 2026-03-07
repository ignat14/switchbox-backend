from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rule import Rule
from app.schemas.rule import RuleCreate
from app.services.audit_service import log_action
from app.services.cdn_publisher import publish_flags
from app.services.flag_service import get_flag


async def add_rule(db: AsyncSession, flag_id: UUID, data: RuleCreate) -> Rule:
    flag = await get_flag(db, flag_id)
    rule = Rule(
        flag_id=flag_id,
        attribute=data.attribute,
        operator=data.operator,
        value=data.value,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    await log_action(
        db, flag_id, "rule_added",
        new_value={"attribute": rule.attribute, "operator": rule.operator},
    )
    await publish_flags(db, flag.project_id, flag.environment)
    return rule


async def remove_rule(db: AsyncSession, rule_id: UUID) -> None:
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    flag = await get_flag(db, rule.flag_id)
    await db.delete(rule)
    await db.commit()
    await log_action(
        db, flag.id, "rule_removed",
        old_value={"attribute": rule.attribute, "operator": rule.operator},
    )
    await publish_flags(db, flag.project_id, flag.environment)
