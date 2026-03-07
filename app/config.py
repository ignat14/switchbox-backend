from typing import Literal
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


def clean_database_url(url: str) -> tuple[str, dict]:
    """Strip libpq params unsupported by asyncpg and return (clean_url, connect_args).

    asyncpg does not accept libpq-style query parameters like ``sslmode``
    or ``channel_binding``.  We strip all non-asyncpg params and convert
    ``sslmode`` into ``connect_args={"ssl": …}``.
    """
    # Parameters that asyncpg's connect() actually accepts.
    asyncpg_params = {
        "host",
        "port",
        "user",
        "password",
        "database",
        "passfile",
        "ssl",
        "direct_tls",
        "connect_timeout",
        "server_settings",
        "target_session_attrs",
    }
    parts = urlsplit(url)
    params = parse_qs(parts.query)
    connect_args: dict = {}
    if params.pop("sslmode", None):
        connect_args["ssl"] = "require"
    # Drop any remaining params that asyncpg doesn't understand.
    params = {k: v for k, v in params.items() if k in asyncpg_params}
    clean_query = urlencode(params, doseq=True)
    clean_url = urlunsplit(parts._replace(query=clean_query))
    return clean_url, connect_args


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ENVIRONMENT: Literal["local", "production"] = "local"
    DATABASE_URL: str


settings = Settings()
