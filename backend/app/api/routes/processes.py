"""REST routes for process monitoring."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser
from app.schemas.metric import ProcessDetail, ProcessInfo
from app.services.process_service import process_service

router = APIRouter(prefix="/processes", tags=["processes"])


@router.get("", response_model=list[ProcessInfo])
def list_processes(
    _: CurrentUser,
    search: str | None = Query(None, description="Filter by process name"),
    sort_by: Literal["cpu", "memory", "name", "pid"] = "cpu",
    descending: bool = True,
    limit: int = Query(100, ge=1, le=1000),
) -> list[ProcessInfo]:
    """List running processes with search and sorting."""
    return process_service.list_processes(
        search=search, sort_by=sort_by, descending=descending, limit=limit
    )


@router.get("/top", response_model=list[ProcessInfo])
def top_consumers(
    _: CurrentUser,
    by: Literal["cpu", "memory"] = "memory",
    limit: int = Query(5, ge=1, le=50),
) -> list[ProcessInfo]:
    """Return the heaviest resource consumers."""
    return process_service.top_consumers(by=by, limit=limit)


@router.get("/{pid}", response_model=ProcessDetail)
def process_detail(pid: int, _: CurrentUser) -> ProcessDetail:
    """Return details for a single process."""
    detail = process_service.get_process(pid)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Process {pid} not found")
    return detail
