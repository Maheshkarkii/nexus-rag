"""Tests for database session management, dependency lifecycle, and connection probing."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import pytest
from app.db.session import check_database_connection
from tests.conftest import test_engine


@pytest.mark.asyncio
async def test_get_db_session_lifecycle(db_session: AsyncSession) -> None:
    """Verify that an active session executes queries and manages transactions."""
    assert isinstance(db_session, AsyncSession)
    assert db_session.is_active

    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_check_database_connection_with_test_engine() -> None:
    """Verify that check_database_connection executes and returns True with an active engine."""
    is_connected, details = await check_database_connection(custom_engine=test_engine)
    assert is_connected is True
    assert details is not None
    assert "SELECT 1 succeeded" in details


@pytest.mark.asyncio
async def test_check_database_connection_probe() -> None:
    """Verify that the database connectivity probe handles unreachable DB safely without exposing credentials."""
    is_connected, details = await check_database_connection(timeout_seconds=0.5)
    assert isinstance(is_connected, bool)
    assert details is not None
    assert "password" not in details.lower()
