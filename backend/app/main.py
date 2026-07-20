"""SystemIQ FastAPI application factory.

Wires together configuration, logging, database bootstrap, routers, WebSocket
endpoints, CORS, exception handling and background tasks.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.websocket import router as ws_router
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.logging_config import configure_logging
from app.services.auth_service import AuthService
from app.services.background import background_manager

logger = logging.getLogger("systemiq.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    configure_logging()
    logger.info("Starting %s (%s)", settings.APP_NAME, settings.ENVIRONMENT)

    # Create tables (dev convenience; production uses Alembic migrations).
    init_db()

    # Bootstrap the first admin account if the user table is empty.
    with SessionLocal() as db:
        AuthService(db).ensure_admin(
            settings.FIRST_ADMIN_USERNAME,
            settings.FIRST_ADMIN_EMAIL,
            settings.FIRST_ADMIN_PASSWORD,
        )

    await background_manager.start()
    try:
        yield
    finally:
        await background_manager.stop()
        logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="AI-Powered System Monitoring and Optimization Platform",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(ws_router)  # WebSocket at /ws/metrics

    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {
            "name": settings.APP_NAME,
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.ENVIRONMENT}

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()
