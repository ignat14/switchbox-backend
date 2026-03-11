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
    R2_PUBLIC_URL: str = ""

    DISCORD_WEBHOOK_URL: str = ""


settings = Settings()
