"""Pytest test fixtures and database isolation for FastAPI backend tests."""

from pathlib import Path
import shutil
import tempfile
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import Settings, get_settings
from app.db.base import Base
import app.db.models  # noqa: F401 Register models for table creation
from app.db.session import get_db
from app.main import app
from app.services.storage import StorageService, get_storage_service

# Isolated In-Memory Async Engine for Unit & Integration Testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
)

test_async_session_factory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Create all database tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated, transactional database session for unit tests."""
    async with test_async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest.fixture(scope="function")
def temp_storage() -> Generator[StorageService, None, None]:
    """Provide an isolated temporary storage directory cleaned up after each test."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_storage_"))
    storage_svc = StorageService(storage_root=temp_dir)
    yield storage_svc
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def client(
    db_session: AsyncSession, temp_storage: StorageService
) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden database and storage dependencies."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    def override_get_storage() -> StorageService:
        return temp_storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_service] = override_get_storage

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def async_client(
    db_session: AsyncSession, temp_storage: StorageService
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTPX async client fixture with overridden database and storage dependencies."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    def override_get_storage() -> StorageService:
        return temp_storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_service] = override_get_storage

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Return test-specific application settings."""
    return get_settings()
