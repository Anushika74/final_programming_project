"""Aggregates all REST routers under the versioned API prefix."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    alerts,
    auth,
    dashboard,
    files,
    hardware,
    logs,
    metrics,
    optimization,
    predictions,
    processes,
    recommendations,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(auth.users_router)
api_router.include_router(dashboard.router)
api_router.include_router(metrics.router)
api_router.include_router(hardware.router)
api_router.include_router(processes.router)
api_router.include_router(recommendations.router)
api_router.include_router(predictions.router)
api_router.include_router(files.router)
api_router.include_router(logs.router)
api_router.include_router(optimization.opt_router)
api_router.include_router(optimization.assistant_router)
api_router.include_router(alerts.router)
