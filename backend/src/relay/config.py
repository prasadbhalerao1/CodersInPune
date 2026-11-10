from decimal import Decimal
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
    # Operator token for /health/ops (aggregate alerting counts). Unset = endpoint hidden.
    ops_token: SecretStr | None = None
    # Email (Resend). Unset key = email off; in-app notifications are unaffected.
    resend_api_key: SecretStr | None = None
    resend_api_base_url: str = "https://api.resend.com"
    email_from: str | None = None  # e.g. "Relay <notifications@mail.example.com>"
    email_reply_to: str | None = None
    # Email via SMTP (takes precedence over Resend when set). Gmail: smtp.gmail.com, 587,
    # starttls, your address as username and a Google app password (not your password).
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    # Fernet key for integration credentials stored at rest (Linear, Notion tokens).
    integration_encryption_key: SecretStr | None = None
    # Structured JSON logs with correlation ids (recommended in production).
    json_logs: bool = False
    # Approved external writes (create-only issues for Relay tasks). Off until the provider
    # permission exists: GitHub App "Issues: Read and write"; Linear OAuth scope that
    # includes "issues:create" (set RELAY_LINEAR_OAUTH_SCOPE and reconnect).
    github_issue_writes: bool = False
    linear_issue_writes: bool = False
    linear_oauth_scope: str = "read"
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
    # AI model providers, tried in order (e.g. "gemini,groq,ollama"); empty = AI off.
    # "fake" is a deterministic test model (local/test only).
    llm_providers: str | None = None
    gemini_key_1: SecretStr | None = None
    gemini_key_2: SecretStr | None = None
    gemini_key_3: SecretStr | None = None
    gemini_key_4: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_url: str = "http://127.0.0.1:11434/v1"
    ollama_model: str | None = None
    llm_timeout_seconds: float = Field(default=90.0, ge=5, le=900)
    ai_monthly_token_budget: int = Field(default=2_000_000, ge=0)
    # USD per million tokens for models missing from the built-in price table (cost reports).
    llm_price_input: Decimal | None = Field(default=None, ge=0)
    llm_price_output: Decimal | None = Field(default=None, ge=0)
    # Activity window for PR/issue metadata and ownership signals.
    github_activity_days: int = Field(default=90, ge=7, le=365)
    worker_shutdown_seconds: float = Field(default=30.0, ge=0, le=600)
    # Run the job worker inside the API process (single-instance free hosting only; a
    # separate `relay-worker` process is the production setup).
    embedded_worker: bool = False

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
        if self.smtp_host and not self.email_from:
            problems.append("Email: RELAY_EMAIL_FROM is required when RELAY_SMTP_HOST is set")
        if bool(self.smtp_username) != bool(self.smtp_password):
            problems.append("Email: set both RELAY_SMTP_USERNAME and RELAY_SMTP_PASSWORD")
        if self.environment in ("staging", "production") and self.smtp_security == "none":
            problems.append("Email: RELAY_SMTP_SECURITY=none is not allowed outside local/test")
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
        providers = self.llm_provider_list
        if "gemini" in providers and not self.gemini_keys:
            problems.append("AI: set RELAY_GEMINI_KEY_1 (to _4) when gemini is a provider")
        if "groq" in providers and self.groq_api_key is None:
            problems.append("AI: set RELAY_GROQ_API_KEY when groq is a provider")
        if "ollama" in providers and not self.ollama_model:
            problems.append("AI: set RELAY_OLLAMA_MODEL when ollama is a provider")
        unknown = set(providers) - {"gemini", "groq", "ollama", "fake"}
        if unknown:
            problems.append(f"AI: unknown provider(s) {', '.join(sorted(unknown))}")
        if "fake" in providers and self.environment in ("staging", "production"):
            problems.append("AI: the fake provider is for local/test only")
        if problems:
            raise ValueError("Invalid Relay configuration: " + "; ".join(problems))
        return self

    @property
    def llm_provider_list(self) -> list[str]:
        return [p.strip().lower() for p in (self.llm_providers or "").split(",") if p.strip()]

    @property
    def gemini_keys(self) -> list[SecretStr]:
        keys = (self.gemini_key_1, self.gemini_key_2, self.gemini_key_3, self.gemini_key_4)
        return [k for k in keys if k is not None]

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
