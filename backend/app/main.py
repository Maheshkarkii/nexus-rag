"""FastAPI application entrypoint for AI Research Assistant."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.schemas.common import ServiceInfoResponse

settings = get_settings()
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Execute startup and shutdown tasks for database engines and vector connections."""
    import time
    t0 = time.perf_counter()
    logger.info("[STARTUP] APP_IMPORT and APP_CREATION completed.")
    logger.info(
        f"[STARTUP] Starting {settings.APP_NAME} in [{settings.APP_ENV}] mode (debug={settings.DEBUG})"
    )
    logger.info(f"[STARTUP] API v1 routes mounted at prefix: {settings.API_V1_STR}")
    logger.info(f"[STARTUP] Allowed CORS origins: {settings.BACKEND_CORS_ORIGINS}")

    # Pre-warm embedding model only if explicitly enabled (prevent OOM on low-memory free tiers like Render 512MB)
    import os

    if os.getenv("PREWARM_MODELS", "false").lower() in ("1", "true", "yes"):
        try:
            import asyncio

            from app.services.embedding import get_embedding_service

            embedding_svc = get_embedding_service()
            asyncio.get_running_loop().run_in_executor(None, embedding_svc.load_model)
            logger.info("[STARTUP] Embedding model pre-warming initiated successfully.")
        except Exception as exc:
            logger.warning(f"[STARTUP] Embedding model pre-warming skipped: {exc}")
    else:
        logger.info("[STARTUP] Lazy model loading enabled (PREWARM_MODELS=false) to conserve memory.")

    t_db = time.perf_counter()
    # Initialize tables for local sqlite dev mode
    from app.db.base import Base
    from app.db.session import engine

    if "sqlite" in str(engine.url):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        db_ms = round((time.perf_counter() - t_db) * 1000, 2)
        logger.info(f"[STARTUP] DATABASE_INITIALIZATION: Initialized local SQLite schema in {db_ms}ms.")

    total_ms = round((time.perf_counter() - t0) * 1000, 2)
    logger.info(f"[STARTUP] STARTUP_COMPLETE in {total_ms}ms")

    yield
    logger.info(f"Shutting down {settings.APP_NAME} gracefully...")


def create_application() -> FastAPI:
    """FastAPI application factory configuring OpenAPI docs, CORS, exceptions, and routers."""
    application = FastAPI(
        title=settings.APP_NAME,
        description=(
            "Production-oriented backend API for the AI Research Assistant platform. "
            "Stage 5 Architecture: Centralized API communication, typed responses, and CORS foundation."
        ),
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # 1. Register centralized exception handlers
    register_exception_handlers(application)

    # 2. Configure CORS middleware with origins from environment
    if settings.BACKEND_CORS_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
            allow_headers=["*"],
        )

    # 3. Mount API v1 router under configured prefix
    application.include_router(api_router, prefix=settings.API_V1_STR)

    # 4. Root service discovery endpoint
    @application.get(
        "/",
        response_model=ServiceInfoResponse,
        tags=["root"],
        summary="Service Discovery & Status",
        description="Provides metadata about the running API service and available documentation links.",
    )
    async def root() -> ServiceInfoResponse:
        return ServiceInfoResponse(
            name=settings.APP_NAME,
            version="0.1.0",
            environment=settings.APP_ENV,
            status="running",
            health=f"{settings.API_V1_STR}/health",
            ready=f"{settings.API_V1_STR}/health/ready",
            docs="/docs" if settings.DEBUG else "disabled",
        )

    return application


app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
