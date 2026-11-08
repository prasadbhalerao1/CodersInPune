from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the API and workers.

    `database_url` must use the restricted application role (no superuser, no BYPASSRLS).
    Migrations use a separate owner role; see `MigrationSettings`.
    """

    model_config = SettingsConfigDict(env_prefix="RELAY_", env_file=".env", extra="ignore")

    environment: Literal["local", "test", "staging", "production"] = "local"
    database_url: str = Field(description="postgresql+psycopg:// URL for the application role")
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_ready_timeout_seconds: float = 2.0
    api_host: str = "127.0.0.1"
    api_port: int = 8000


class MigrationSettings(BaseSettings):
    """Settings used only by Alembic. Never loaded by the running application."""

    model_config = SettingsConfigDict(env_prefix="RELAY_", env_file=".env", extra="ignore")

    migration_database_url: str = Field(description="postgresql+psycopg:// URL for the owner role")
    app_db_role: str = Field(default="relay_app", pattern=r"^[a-z_][a-z0-9_]{0,62}$")
