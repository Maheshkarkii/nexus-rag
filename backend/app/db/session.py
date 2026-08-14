"""SQLAlchemy 2.x asynchronous database engine, session factory, and dependency."""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import get_settings

logger = logging.getLogger("ai_research_assistant.db")
settings = get_settings()

# ==============================================================================
# Database Engine Initialization
# ==============================================================================
engine_kwargs = {
    "echo": settings.DEBUG and settings.APP_ENV == "development",
    "future": True,
}

if "sqlite" not in settings.async_database_url:
    engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
            "pool_timeout": 30,
        }
    )

engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    **engine_kwargs,
)

# Thread-safe async session factory
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


def get_async_session_factory(
    custom_engine: Optional[AsyncEngine] = None,
) -> async_sessionmaker[AsyncSession]:
    """Return an async session factory bound to the provided or default engine."""
    target_engine = custom_engine or engine
    return async_sessionmaker(
        bind=target_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# ==============================================================================
# FastAPI Database Session Dependency
# ==============================================================================
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an isolated AsyncSession per request."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ==============================================================================
# Database Health & Connectivity Checker
# ==============================================================================
async def check_database_connection(
    custom_engine: Optional[AsyncEngine] = None,
    timeout_seconds: float = 3.0,
) -> Tuple[bool, Optional[str]]:
    """Safely execute a lightweight SELECT 1 query to verify database connectivity."""
    target_engine = custom_engine or engine
    try:
        async with asyncio.timeout(timeout_seconds):
            async with target_engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                row = result.scalar()
                if row == 1:
                    return True, "PostgreSQL connected and responsive (SELECT 1 succeeded)"
                return False, "Unexpected query response from database"
    except asyncio.TimeoutError:
        logger.warning("Database health check timed out.")
        return False, "Database connection timed out"
    except Exception as exc:
        err_msg = type(exc).__name__
        logger.warning(f"Database readiness check failed: {err_msg}")
        return False, f"Database connection unavailable ({err_msg})"
