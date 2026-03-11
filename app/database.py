from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# libpq query params that asyncpg does not accept.
_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding", "sslrootcert", "sslcert", "sslkey"}


def clean_database_url(url: str) -> tuple[str, dict]:
    """Strip libpq-only params from a database URL for asyncpg compatibility."""
    parts = urlsplit(url)
    params = parse_qs(parts.query)
    connect_args: dict = {}
    if params.pop("sslmode", None):
        connect_args["ssl"] = "require"
    for key in _LIBPQ_ONLY_PARAMS:
        params.pop(key, None)
    clean_query = urlencode(params, doseq=True)
    clean_url = urlunsplit(parts._replace(query=clean_query))
    return clean_url, connect_args


_url, _connect_args = clean_database_url(settings.DATABASE_URL)

engine = create_async_engine(_url, connect_args=_connect_args, pool_pre_ping=True)

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session() as session:
        yield session
