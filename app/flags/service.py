from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import log_action
from app.environments.models import Environment
from app.flags.cdn_publisher import publish_flags
from app.flags.models import Flag, FlagEnvironment
from app.flags.schemas import FlagCreate, FlagEnvironmentUpdate, FlagUpdate


def _flag_query():
    """Return a base select for Flag with all nested relationships eagerly loaded."""
    return select(Flag).options(
        selectinload(Flag.project),
        selectinload(Flag.flag_environments)
        .selectinload(FlagEnvironment.rules),
        selectinload(Flag.flag_environments)
        .selectinload(FlagEnvironment.environment),
    )


def _fe_query():
    """Return a base select for FlagEnvironment with relationships eagerly loaded."""
    return select(FlagEnvironment).options(
        selectinload(FlagEnvironment.rules),
        selectinload(FlagEnvironment.environment),
    )


def _fe_to_dict(fe: FlagEnvironment) -> dict:
    return {
        "id": str(fe.id),
        "environment_id": str(fe.environment_id),
        "environment_name": fe.environment.name,
        "enabled": fe.enabled,
        "rollout_pct": fe.rollout_pct,
        "default_value": fe.default_value,
        "rules": [
            {
                "id": str(r.id),
                "attribute": r.attribute,
                "operator": r.operator,
                "value": r.value,
                "created_at": r.created_at,
            }
            for r in fe.rules
        ],
    }


def _flag_to_dict(flag: Flag) -> dict:
    return {
        "id": str(flag.id),
        "project_id": str(flag.project_id),
        "project_name": flag.project.name if flag.project else None,
        "key": flag.key,
        "name": flag.name,
        "flag_type": flag.flag_type,
        "created_at": flag.created_at,
        "updated_at": flag.updated_at,
        "environments": [_fe_to_dict(fe) for fe in flag.flag_environments],
    }


async def _load_flag(db: AsyncSession, flag_id: UUID) -> Flag:
    """Load a flag with all nested relationships."""
    result = await db.execute(_flag_query().where(Flag.id == flag_id))
    flag = result.scalar_one_or_none()
    if flag is None:
        raise HTTPException(status_code=404, detail="Flag not found")
    return flag


async def create_flag(
    db: AsyncSession, project_id: UUID, data: FlagCreate, changed_by: str | None = None
) -> dict:
    flag = Flag(
        project_id=project_id,
        key=data.key,
        name=data.name,
        flag_type=data.flag_type,
    )
    db.add(flag)
    await db.flush()

    result = await db.execute(
        select(Environment).where(Environment.project_id == project_id)
    )
    environments = result.scalars().all()
    for env in environments:
        fe = FlagEnvironment(
            flag_id=flag.id,
            environment_id=env.id,
            default_value=data.default_value,
        )
        db.add(fe)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    flag = await _load_flag(db, flag.id)
    await log_action(db, flag.id, "created", new_value={"key": flag.key}, changed_by=changed_by)

    for env in environments:
        await publish_flags(db, project_id, env.id, env.name)

    return _flag_to_dict(flag)


async def list_flags(db: AsyncSession, project_id: UUID) -> list[dict]:
    result = await db.execute(
        _flag_query()
        .where(Flag.project_id == project_id)
        .order_by(Flag.created_at.desc())
    )
    flags = result.scalars().all()
    return [_flag_to_dict(f) for f in flags]


async def get_flag(db: AsyncSession, flag_id: UUID) -> Flag:
    return await _load_flag(db, flag_id)


async def get_flag_response(db: AsyncSession, flag_id: UUID) -> dict:
    flag = await _load_flag(db, flag_id)
    return _flag_to_dict(flag)


async def update_flag(
    db: AsyncSession, flag_id: UUID, data: FlagUpdate, changed_by: str | None = None
) -> dict:
    flag = await _load_flag(db, flag_id)
    old = {"name": flag.name}
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(flag, field, value)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    flag = await _load_flag(db, flag_id)
    new = {"name": flag.name}
    await log_action(db, flag_id, "updated", old_value=old, new_value=new, changed_by=changed_by)
    return _flag_to_dict(flag)


async def get_flag_environment(db: AsyncSession, flag_env_id: UUID) -> FlagEnvironment:
    result = await db.execute(_fe_query().where(FlagEnvironment.id == flag_env_id))
    fe = result.scalar_one_or_none()
    if fe is None:
        raise HTTPException(status_code=404, detail="Flag environment not found")
    return fe


async def update_flag_environment(
    db: AsyncSession, flag_env_id: UUID, data: FlagEnvironmentUpdate, changed_by: str | None = None
) -> dict:
    fe = await get_flag_environment(db, flag_env_id)
    flag_id = fe.flag_id
    old = {"rollout_pct": fe.rollout_pct, "default_value": fe.default_value}
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(fe, field, value)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    fe = await get_flag_environment(db, flag_env_id)
    new = {"rollout_pct": fe.rollout_pct, "default_value": fe.default_value}
    await log_action(
        db, flag_id, "env_updated",
        old_value={**old, "environment": fe.environment.name},
        new_value={**new, "environment": fe.environment.name},
        changed_by=changed_by,
    )
    flag = await _load_flag(db, flag_id)
    await publish_flags(db, flag.project_id, fe.environment_id, fe.environment.name)
    return _flag_to_dict(flag)


async def toggle_flag_environment(
    db: AsyncSession, flag_env_id: UUID, changed_by: str | None = None
) -> dict:
    fe = await get_flag_environment(db, flag_env_id)
    flag_id = fe.flag_id
    old_enabled = fe.enabled
    fe.enabled = not fe.enabled
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    fe = await get_flag_environment(db, flag_env_id)
    await log_action(
        db, flag_id, "toggled",
        old_value={"enabled": old_enabled, "environment": fe.environment.name},
        new_value={"enabled": fe.enabled, "environment": fe.environment.name},
        changed_by=changed_by,
    )
    flag = await _load_flag(db, flag_id)
    await publish_flags(db, flag.project_id, fe.environment_id, fe.environment.name)
    return _flag_to_dict(flag)


async def delete_flag(db: AsyncSession, flag_id: UUID) -> None:
    flag = await _load_flag(db, flag_id)
    project_id = flag.project_id
    env_info = [(fe.environment_id, fe.environment.name) for fe in flag.flag_environments]
    await db.delete(flag)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    for env_id, env_name in env_info:
        await publish_flags(db, project_id, env_id, env_name)
