from typing import Literal
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


def clean_database_url(url: str) -> tuple[str, dict]:
    """Strip sslmode from URL and return (clean_url, connect_args).

    asyncpg does not support ``sslmode`` as a query-string parameter;
    it must be passed via ``connect_args={"ssl": …}`` instead.
    """
    parts = urlsplit(url)
    params = parse_qs(parts.query)
    connect_args: dict = {}
    if params.pop("sslmode", None):
        connect_args["ssl"] = "require"
    clean_query = urlencode(params, doseq=True)
    clean_url = urlunsplit(parts._replace(query=clean_query))
    return clean_url, connect_args


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ENVIRONMENT: Literal["local", "production"] = "local"
    DATABASE_URL: str


settings = Settings()
