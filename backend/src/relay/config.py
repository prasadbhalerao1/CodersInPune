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

    # WorkOS AuthKit access-token verification. Issuer and JWKS URL derive from the
    # client ID (WorkOS docs: iss = {api}/user_management/{client_id},
    # JWKS = {api}/sso/jwks/{client_id}); override only for a custom auth domain.
    workos_client_id: str = Field(pattern=r"^client_[A-Za-z0-9_]+$")
    workos_api_base_url: str = "https://api.workos.com"
    workos_issuer: str | None = None
    workos_jwks_url: str | None = None
    # WorkOS does not document an `aud` claim. If tokens ever carry one, set it here;
    # until then a token *with* an audience is rejected.
    workos_audience: str | None = None
    jwt_algorithms: list[str] = ["RS256"]
    jwt_leeway_seconds: int = Field(default=10, ge=0, le=60)
    jwks_cache_seconds: int = Field(default=600, ge=30)
    jwks_refresh_cooldown_seconds: int = Field(default=30, ge=1)

    @property
    def resolved_workos_issuer(self) -> str:
        return self.workos_issuer or (
            f"{self.workos_api_base_url}/user_management/{self.workos_client_id}"
        )

    @property
    def resolved_workos_jwks_url(self) -> str:
        return (
            self.workos_jwks_url or f"{self.workos_api_base_url}/sso/jwks/{self.workos_client_id}"
        )


class MigrationSettings(BaseSettings):
    """Settings used only by Alembic. Never loaded by the running application."""

    model_config = SettingsConfigDict(env_prefix="RELAY_", env_file=".env", extra="ignore")

    migration_database_url: str = Field(description="postgresql+psycopg:// URL for the owner role")
    app_db_role: str = Field(default="relay_app", pattern=r"^[a-z_][a-z0-9_]{0,62}$")
