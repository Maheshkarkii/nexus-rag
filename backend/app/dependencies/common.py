"""Common reusable FastAPI dependencies."""

from typing import Annotated
from fastapi import Depends, Header, Request
from app.core.config import Settings, get_settings


def get_app_settings() -> Settings:
    """Dependency injecting application settings."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


async def get_request_id(
    x_request_id: Annotated[str | None, Header(description="Optional client request trace ID")] = None,
) -> str:
    """Extract or return client request ID for logging and request tracing."""
    return x_request_id or "local-dev-request"


RequestIdDep = Annotated[str, Depends(get_request_id)]
