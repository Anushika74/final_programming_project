"""REST routes for alerts."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.insight import AlertRead
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertRead])
def list_alerts(
    _: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
    only_unresolved: bool = False,
) -> list[AlertRead]:
    alerts = AlertService(db).list_alerts(limit=limit, only_unresolved=only_unresolved)
    return [AlertRead.model_validate(a) for a in alerts]


@router.post("/{alert_id}/resolve", response_model=AlertRead)
def resolve_alert(alert_id: int, _: CurrentUser, db: DbSession) -> AlertRead:
    alert = AlertService(db).resolve(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertRead.model_validate(alert)
