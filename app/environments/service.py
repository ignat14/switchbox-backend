from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.environments.models import Environment, generate_sdk_key
from app.environments.schemas import EnvironmentCreate, EnvironmentUpdate


DEFAULT_ENVIRONMENTS = ["development", "production"]

SDK_KEY_GRACE_PERIOD = timedelta(hours=24)


async def create_default_environments(db: AsyncSession, project_id: UUID) -> list[Environment]:
    envs = []
    for name in DEFAULT_ENVIRONMENTS:
        env = Environment(project_id=project_id, name=name)
        db.add(env)
        envs.append(env)
    await db.flush()
    return envs


async def list_environments(db: AsyncSession, project_id: UUID) -> list[Environment]:
    result = await db.execute(
        select(Environment)
        .where(Environment.project_id == project_id)
        .order_by(Environment.created_at)
    )
    return list(result.scalars().all())


async def get_environment(db: AsyncSession, environment_id: UUID) -> Environment:
    result = await db.execute(
        select(Environment).where(Environment.id == environment_id)
    )
    env = result.scalar_one_or_none()
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return env


async def create_environment(
    db: AsyncSession, project_id: UUID, data: EnvironmentCreate
) -> Environment:
    env = Environment(project_id=project_id, name=data.name)
    db.add(env)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(env)

    # Create flag_environments for all existing flags in this project
    from app.flags.models import Flag, FlagEnvironment
    result = await db.execute(select(Flag).where(Flag.project_id == project_id))
    flags = result.scalars().all()
    for flag in flags:
        fe = FlagEnvironment(flag_id=flag.id, environment_id=env.id)
        db.add(fe)
    if flags:
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return env


async def update_environment(
    db: AsyncSession, environment_id: UUID, data: EnvironmentUpdate
) -> Environment:
    env = await get_environment(db, environment_id)
    env.name = data.name
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(env)
    return env


async def rotate_sdk_key(db: AsyncSession, environment_id: UUID) -> Environment:
    """Rotate the SDK key for an environment.

    The old key is preserved as previous_sdk_key with a grace period,
    during which CDN content is published to both paths.
    """
    env = await get_environment(db, environment_id)
    old_sdk_key = env.sdk_key

    env.previous_sdk_key = old_sdk_key
    env.previous_sdk_key_expires_at = datetime.now(timezone.utc) + SDK_KEY_GRACE_PERIOD
    env.sdk_key = generate_sdk_key()

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(env)

    # Republish — publish_flags automatically publishes to previous_sdk_key
    # during the grace period
    from app.flags.cdn_publisher import publish_flags
    await publish_flags(db, env.project_id, env.id, env.sdk_key)

    return env


async def delete_environment(db: AsyncSession, environment_id: UUID) -> None:
    env = await get_environment(db, environment_id)

    # Check it's not the last environment for this project
    count_result = await db.execute(
        select(Environment).where(Environment.project_id == env.project_id)
    )
    all_envs = count_result.scalars().all()
    if len(all_envs) <= 1:
        raise HTTPException(
            status_code=400, detail="Cannot delete the last environment"
        )

    await db.delete(env)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
