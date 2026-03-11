from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.environments.models import Environment
from app.environments.schemas import EnvironmentCreate, EnvironmentUpdate


DEFAULT_ENVIRONMENTS = ["development", "production"]


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
    result = await db.execute(
        select(Environment).where(Environment.id == environment_id)
    )
    env = result.scalar_one_or_none()
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    env.name = data.name
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(env)
    return env


async def delete_environment(db: AsyncSession, environment_id: UUID) -> None:
    result = await db.execute(
        select(Environment).where(Environment.id == environment_id)
    )
    env = result.scalar_one_or_none()
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")

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
