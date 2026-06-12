from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ENVIRONMENT: Literal["local", "production"] = "local"
    DATABASE_URL: str

    ADMIN_TOKEN: str = ""

    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "switchbox-configs"

    # Cloudflare KV read access for the SDK connection badge (Phase 4).
    # The KV namespace is written by switchbox-worker-cdn (conn:{sdk_key}).
    CF_KV_API_TOKEN: str = ""
    CF_KV_NAMESPACE_ID: str = ""

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    JWT_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:5173"

    DISCORD_WEBHOOK_URL: str = ""

    SENTRY_DSN: str = ""


settings = Settings()
