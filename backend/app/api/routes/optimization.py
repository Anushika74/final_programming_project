"""REST routes for optimization actions and the NL assistant."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.context import SystemContext
from app.schemas.insight import (
    AssistantQuery,
    AssistantResponse,
    OptimizationAction,
    OptimizationRequest,
    OptimizationResult,
)
from app.services.context_service import SystemContextService
from app.services.nl_service import NLService
from app.services.optimization_service import optimization_service

opt_router = APIRouter(prefix="/optimization", tags=["optimization"])
assistant_router = APIRouter(prefix="/assistant", tags=["assistant"])


@opt_router.get("/actions", response_model=list[OptimizationAction])
def list_actions(_: CurrentUser) -> list[OptimizationAction]:
    """List available, confirmation-gated optimization actions."""
    return optimization_service.list_actions()


@opt_router.post("/execute", response_model=OptimizationResult)
def execute_action(request: OptimizationRequest, _: CurrentUser) -> OptimizationResult:
    """Execute (or dry-run) an optimization action. Confirmation required to apply."""
    return optimization_service.execute(
        action_key=request.action_key, confirm=request.confirm, dry_run=request.dry_run
    )


@assistant_router.post("/ask", response_model=AssistantResponse)
def ask_assistant(query: AssistantQuery, _: CurrentUser, db: DbSession) -> AssistantResponse:
    """Ask the AI assistant a natural-language question about the system.

    The assistant gathers a complete SystemContext (metrics, hardware, processes,
    predictions, recommendations, alerts, logs) and reasons over it before
    answering — performing root-cause analysis rather than echoing raw values.
    """
    return NLService(db).handle(query.query)


@assistant_router.get("/context", response_model=SystemContext)
def assistant_context(_: CurrentUser, db: DbSession, predictions: bool = True) -> SystemContext:
    """Return the consolidated System Context the assistant reasons over.

    Useful for the UI's "context the AI used" panel and for debugging. Set
    `predictions=false` for a faster response that skips ML forecasting.
    """
    return SystemContextService(db).build(include_predictions=predictions)
