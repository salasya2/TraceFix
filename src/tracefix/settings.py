from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from tracefix._paths import ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = Field(default="development", alias="TRACEFIX_ENV")
    profile: str = Field(default="embedded", alias="TRACEFIX_PROFILE")
    log_level: str = Field(default="INFO", alias="TRACEFIX_LOG_LEVEL")
    auth_mode: str = Field(default="dev", alias="TRACEFIX_AUTH_MODE")
    secret_key: str = Field(default="dev-secret-change-me-please-32b", alias="TRACEFIX_SECRET_KEY")
    dev_user_email: str = Field(default="maintainer@tracefix.local", alias="TRACEFIX_DEV_USER_EMAIL")
    dev_user_role: str = Field(default="owner", alias="TRACEFIX_DEV_USER_ROLE")

    api_host: str = Field(default="127.0.0.1", alias="TRACEFIX_API_HOST")
    api_port: int = Field(default=8080, alias="TRACEFIX_API_PORT")
    public_url: str = Field(default="http://127.0.0.1:8080", alias="TRACEFIX_PUBLIC_URL")
    web_origin: str = Field(default="http://127.0.0.1:5173", alias="TRACEFIX_WEB_ORIGIN")

    database_url: str = Field(default="sqlite+aiosqlite:///" + str(ROOT / ".data" / "tracefix.db"))
    artifact_backend: str = Field(default="local", alias="TRACEFIX_ARTIFACT_BACKEND")
    artifact_dir: Path = Field(default=ROOT / ".data" / "artifacts", alias="TRACEFIX_ARTIFACT_DIR")
    s3_bucket: str = Field(default="tracefix-artifacts", alias="TRACEFIX_S3_BUCKET")

    orchestrator: str = Field(default="local", alias="TRACEFIX_ORCHESTRATOR")
    temporal_address: str = Field(default="127.0.0.1:7233", alias="TEMPORAL_ADDRESS")
    temporal_namespace: str = Field(default="tracefix", alias="TEMPORAL_NAMESPACE")

    executor: str = Field(default="process", alias="TRACEFIX_EXECUTOR")
    python_bin: str = Field(default="python", alias="TRACEFIX_PYTHON_BIN")

    model_provider: str = Field(default="fixture", alias="TRACEFIX_MODEL_PROVIDER")
    model_id: str = Field(default="grok-4.5", alias="TRACEFIX_MODEL_ID")
    prompt_version: str = Field(default="v1", alias="TRACEFIX_PROMPT_VERSION")
    xai_api_key: str = Field(default="", alias="XAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    model_base_url: str = Field(default="https://api.x.ai/v1", alias="TRACEFIX_MODEL_BASE_URL")

    github_app_id: str = Field(default="", alias="GITHUB_APP_ID")
    github_webhook_secret: str = Field(default="dev-webhook-secret-change-me", alias="GITHUB_WEBHOOK_SECRET")
    github_api_version: str = Field(default="2022-11-28", alias="GITHUB_API_VERSION")

    oidc_issuer: str = Field(default="", alias="OIDC_ISSUER")
    oidc_client_id: str = Field(default="", alias="OIDC_CLIENT_ID")
    oidc_client_secret: str = Field(default="", alias="OIDC_CLIENT_SECRET")
    oidc_audience: str = Field(default="tracefix", alias="OIDC_AUDIENCE")

    default_reserved_model_usd: float = Field(default=2.0, alias="TRACEFIX_DEFAULT_RESERVED_MODEL_USD")
    global_max_concurrent_runs: int = Field(default=20, alias="TRACEFIX_GLOBAL_MAX_CONCURRENT_RUNS")

    @property
    def is_production(self) -> bool:
        return self.env == "production"


def load_settings() -> Settings:
    return Settings()
