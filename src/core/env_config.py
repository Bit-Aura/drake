import os
import logging
from functools import lru_cache
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class AppSettings(BaseModel):
    """
    Centralized configuration.
    Fail-close: Application will crash at startup if required variables are missing.
    No local developer fallbacks are allowed here.
    """
    DELL_MCP_API_KEY: str = Field(..., description="API Key for MCP server authorization")
    JWT_SECRET: str = Field(..., description="Secret for JWT signing")
    CORS_ORIGINS: str = Field(..., description="Comma-separated list of allowed CORS origins")

    DELL_EXECUTOR_TYPE: str = Field(..., description="Type of executor (prism, httpx, etc)")
    PRISM_URL: str = Field(..., description="Stoplight Prism URL")
    MOCK_SERVER_URL: str = Field(..., description="Fallback mock server URL")

    DELL_COMPATIBILITY_POLICY: str = Field(..., description="Policy STRICT or LAX")

    DELL_CACHE_TTL: int = Field(60, description="Cache TTL in seconds")

    ADMIN_EMAIL: str = Field(..., description="Admin portal email")
    ADMIN_PASSWORD: str = Field(..., description="Admin portal password")

    IDRAC_USER: str = Field(..., description="Default iDRAC User")
    IDRAC_PASSWORD: str = Field(..., description="Default iDRAC Password")

    OMSDK_SESSION_TOKEN: str = Field(..., description="Session token for OMSDK")

    OPENAI_API_KEY: str = Field(..., description="OpenAI API Key")
    LLM_BASE_URL: str = Field(..., description="LLM Base URL")
    LLM_MODEL: str = Field(..., description="LLM Model Name")

    PORT: int = Field(8000, description="Server port")

    model_config = {"extra": "ignore"}


def _load_settings() -> AppSettings:
    """
    Build settings from current os.environ snapshot.
    Called on every attribute access so that ``patch.dict(os.environ, ...)``
    in tests works correctly. Pydantic construction is cheap (~µs).
    Raises ``SystemExit`` if required variables are missing — fail-close.
    """
    try:
        return AppSettings(**os.environ)
    except ValidationError as e:
        logger.critical(
            "STARTUP INTEGRITY FAILURE. Missing or invalid environment variables: %s", e
        )
        raise SystemExit(
            f"CRITICAL: Failed to start due to invalid configuration.\n{e}"
        )


class _SettingsProxy:
    """
    Transparent proxy that rebuilds ``AppSettings`` on every attribute
    access from the live ``os.environ``.  This keeps ``patch.dict``
    compatibility in tests while still enforcing fail-close validation.
    """
    def __getattr__(self, name: str):
        return getattr(_load_settings(), name)


settings = _SettingsProxy()
