"""REST routes for AI recommendations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.insight import RecommendationRead
from app.services.monitoring_service import monitoring_service
from app.services.process_service import process_service
from app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=list[RecommendationRead])
def list_recommendations(
    _: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
    only_unacknowledged: bool = False,
) -> list[RecommendationRead]:
    recs = RecommendationService(db).list_recommendations(
        limit=limit, only_unacknowledged=only_unacknowledged
    )
    return [RecommendationRead.model_validate(r) for r in recs]


@router.post("/generate", response_model=list[RecommendationRead])
def generate_recommendations(_: CurrentUser, db: DbSession) -> list[RecommendationRead]:
    """Force an on-demand evaluation against the current system state."""
    snapshot = monitoring_service.collect()
    top = process_service.top_consumers(by="memory", limit=10)
    stored = RecommendationService(db).generate_and_store(snapshot, top)
    return [RecommendationRead.model_validate(r) for r in stored]


@router.post("/{rec_id}/acknowledge", response_model=RecommendationRead)
def acknowledge(rec_id: int, _: CurrentUser, db: DbSession) -> RecommendationRead:
    rec = RecommendationService(db).acknowledge(rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return RecommendationRead.model_validate(rec)
