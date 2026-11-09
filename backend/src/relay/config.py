from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    worker_concurrency: int = Field(default=1, ge=1, le=16)

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
    # Server-side WorkOS API key: verified user emails and invitation emails. Never sent to
    # the browser. Without it, invitations cannot be accepted (the email can't be verified).
    workos_api_key: SecretStr | None = None
    frontend_base_url: str = "http://localhost:3000"
    invitation_ttl_days: int = Field(default=7, ge=1, le=30)

    # GitHub App (organisation installation). Private key and client secret stay server-side.
    github_app_id: str | None = None
    github_app_slug: str | None = None
    github_client_id: str | None = None
    github_client_secret: SecretStr | None = None
    github_private_key: SecretStr | None = None
    github_api_base_url: str = "https://api.github.com"
    github_web_base_url: str = "https://github.com"
    # Webhook HMAC secret (App settings > Webhook secret). Unset = webhooks rejected (503).
    github_webhook_secret: SecretStr | None = None
    # Email (Resend). Unset key = email off; in-app notifications are unaffected.
    resend_api_key: SecretStr | None = None
    resend_api_base_url: str = "https://api.resend.com"
    email_from: str | None = None  # e.g. "Relay <notifications@mail.example.com>"
    email_reply_to: str | None = None
    # Fernet key for integration credentials stored at rest (Linear, Notion tokens).
    integration_encryption_key: SecretStr | None = None
    # Linear OAuth app (read scope). Redirect URI: {frontend}/integrations/linear/callback
    linear_client_id: str | None = None
    linear_client_secret: SecretStr | None = None
    linear_api_url: str = "https://api.linear.app/graphql"
    linear_oauth_url: str = "https://linear.app/oauth/authorize"
    linear_token_url: str = "https://api.linear.app/oauth/token"  # noqa: S105  (a URL)
    # Notion public integration (read content). Redirect: {frontend}/integrations/notion/callback
    notion_client_id: str | None = None
    notion_client_secret: SecretStr | None = None
    notion_api_url: str = "https://api.notion.com/v1"
    notion_page_limit: int = Field(default=500, ge=1, le=5000)
    # Activity window for PR/issue metadata and ownership signals.
    github_activity_days: int = Field(default=90, ge=7, le=365)
    worker_shutdown_seconds: float = Field(default=30.0, ge=0, le=600)

    @field_validator("*", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: Any) -> Any:
        # `RELAY_X=` (as in .env.example) means "not configured", not an empty secret.
        return None if value == "" else value

    @model_validator(mode="after")
    def _deployable(self) -> Settings:
        """Fail fast on misconfiguration instead of half-working in production.

        Partial integration configuration is an error in every environment (it would show
        as "configured" and then fail at runtime); staging and production also require
        HTTPS links, the WorkOS API key and a non-local database.
        """
        problems: list[str] = []
        pairs = {
            "Linear": (self.linear_client_id, self.linear_client_secret),
            "Notion": (self.notion_client_id, self.notion_client_secret),
        }
        for name, (client_id, secret) in pairs.items():
            if bool(client_id) != bool(secret):
                problems.append(f"{name}: set both the client ID and the client secret")
        if self.resend_api_key and not self.email_from:
            problems.append("Email: RELAY_EMAIL_FROM is required when RELAY_RESEND_API_KEY is set")
        github = (self.github_app_id, self.github_private_key, self.github_client_secret)
        if any(github) and not all(github):
            problems.append(
                "GitHub: set RELAY_GITHUB_APP_ID, RELAY_GITHUB_PRIVATE_KEY and "
                "RELAY_GITHUB_CLIENT_SECRET together"
            )
        if self.environment in ("staging", "production"):
            if not self.frontend_base_url.startswith("https://"):
                problems.append("RELAY_FRONTEND_BASE_URL must use https:// outside local/test")
            if self.workos_api_key is None:
                problems.append("RELAY_WORKOS_API_KEY is required outside local/test")
            if any(pair[0] for pair in pairs.values()) and not self.integration_encryption_key:
                problems.append(
                    "RELAY_INTEGRATION_ENCRYPTION_KEY is required when Linear or Notion is set"
                )
        if problems:
            raise ValueError("Invalid Relay configuration: " + "; ".join(problems))
        return self

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
