"""REST routes for the file analyzer."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser
from app.schemas.insight import FileScanRequest, FileScanResult
from app.services.file_analyzer_service import file_analyzer_service

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/scan", response_model=FileScanResult)
def scan_directory(request: FileScanRequest, _: CurrentUser) -> FileScanResult:
    """Analyze a directory for large/duplicate/temp files and empty folders.

    The scan is read-only; nothing is deleted here.
    """
    try:
        return file_analyzer_service.scan(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
