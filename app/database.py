from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import clean_database_url, settings

_url, _connect_args = clean_database_url(settings.DATABASE_URL)

engine = create_async_engine(_url, connect_args=_connect_args)

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session() as session:
        yield session
