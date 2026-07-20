"""REST routes for the log analyzer."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.insight import LogAnalysisSummary, LogAnalyzeRequest, LogEntryRead
from app.services.log_analyzer_service import LogAnalyzerService

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("/analyze", response_model=LogAnalysisSummary)
def analyze_logs(request: LogAnalyzeRequest, _: CurrentUser, db: DbSession) -> LogAnalysisSummary:
    """Analyze pasted log content and return human-readable explanations."""
    return LogAnalyzerService(db).analyze(request.content, source=request.source)


@router.get("/recent", response_model=list[LogEntryRead])
def recent_logs(
    _: CurrentUser,
    db: DbSession,
    limit: int = Query(100, ge=1, le=500),
) -> list[LogEntryRead]:
    """Return recently analyzed (notable) log entries."""
    entries = LogAnalyzerService(db).recent_entries(limit=limit)
    return [LogEntryRead.model_validate(e) for e in entries]
