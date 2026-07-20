"""Optimization service.

Provides a catalogue of *safe*, confirmation-gated optimization actions. Every
action:
  * is described with a clear risk level,
  * defaults to a **dry run** (reports what *would* happen),
  * requires explicit `confirm=True` to actually execute,
  * never touches files outside well-known temporary locations.

This conservative design is appropriate for an automated system tool: the user
always stays in control.
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from pathlib import Path

import psutil

from app.schemas.insight import OptimizationAction, OptimizationResult

logger = logging.getLogger(__name__)


# Catalogue of supported actions.
ACTIONS: dict[str, OptimizationAction] = {
    "clean_temp_files": OptimizationAction(
        key="clean_temp_files",
        title="Clean temporary files",
        description=(
            "Remove stale files from the user temporary directory that are older "
            "than 24 hours."
        ),
        risk="low",
        estimated_impact="Frees disk space",
    ),
    "clear_memory_cache": OptimizationAction(
        key="clear_memory_cache",
        title="Clear memory cache (advisory)",
        description=(
            "Report cache memory usage and advise on freeing it. Dropping kernel "
            "caches requires root and is intentionally not performed automatically."
        ),
        risk="low",
        estimated_impact="Advisory only",
    ),
    "analyze_startup": OptimizationAction(
        key="analyze_startup",
        title="Analyze startup applications",
        description="List enabled startup/long-running services for review.",
        risk="low",
        estimated_impact="Insight only",
    ),
    "optimize_resources": OptimizationAction(
        key="optimize_resources",
        title="Resource optimization suggestions",
        description="Identify the heaviest processes and suggest actions.",
        risk="low",
        estimated_impact="Insight only",
    ),
}

# Temp directory we are allowed to clean. Restricted for safety.
_SAFE_TEMP_DIR = Path(tempfile.gettempdir())
_STALE_SECONDS = 24 * 60 * 60


class OptimizationService:
    """Lists and executes confirmation-gated optimization actions."""

    def list_actions(self) -> list[OptimizationAction]:
        return list(ACTIONS.values())

    def execute(self, action_key: str, confirm: bool, dry_run: bool) -> OptimizationResult:
        action = ACTIONS.get(action_key)
        if action is None:
            return OptimizationResult(
                action_key=action_key,
                executed=False,
                dry_run=dry_run,
                message=f"Unknown action '{action_key}'.",
            )

        if action.requires_confirmation and not confirm and not dry_run:
            return OptimizationResult(
                action_key=action_key,
                executed=False,
                dry_run=dry_run,
                message="This action requires confirmation (set confirm=true).",
            )

        handler = {
            "clean_temp_files": self._clean_temp_files,
            "clear_memory_cache": self._clear_memory_cache,
            "analyze_startup": self._analyze_startup,
            "optimize_resources": self._optimize_resources,
        }[action_key]
        return handler(confirm=confirm, dry_run=dry_run)

    # ---- Handlers ----
    def _clean_temp_files(self, confirm: bool, dry_run: bool) -> OptimizationResult:
        now = time.time()
        candidates: list[tuple[Path, int]] = []
        reclaimable = 0
        for entry in _SAFE_TEMP_DIR.glob("*"):
            try:
                if not entry.is_file():
                    continue
                stat = entry.stat()
                if now - stat.st_mtime < _STALE_SECONDS:
                    continue
                candidates.append((entry, stat.st_size))
                reclaimable += stat.st_size
            except (OSError, PermissionError):
                continue

        if dry_run or not confirm:
            return OptimizationResult(
                action_key="clean_temp_files",
                executed=False,
                dry_run=True,
                message=(
                    f"Dry run: {len(candidates)} stale temp file(s) totalling "
                    f"{reclaimable / (1024*1024):.1f} MB would be removed from "
                    f"{_SAFE_TEMP_DIR}."
                ),
                details={"file_count": len(candidates), "reclaimable_bytes": reclaimable},
            )

        removed, freed, errors = 0, 0, 0
        for path, size in candidates:
            try:
                path.unlink()
                removed += 1
                freed += size
            except (OSError, PermissionError):
                errors += 1
        logger.info("clean_temp_files removed %d files (%d bytes)", removed, freed)
        return OptimizationResult(
            action_key="clean_temp_files",
            executed=True,
            dry_run=False,
            message=(
                f"Removed {removed} temp file(s), freed "
                f"{freed / (1024*1024):.1f} MB ({errors} skipped)."
            ),
            details={"removed": removed, "freed_bytes": freed, "errors": errors},
        )

    def _clear_memory_cache(self, confirm: bool, dry_run: bool) -> OptimizationResult:
        vmem = psutil.virtual_memory()
        cached_mb = getattr(vmem, "cached", 0) / (1024 * 1024)
        available_mb = vmem.available / (1024 * 1024)
        return OptimizationResult(
            action_key="clear_memory_cache",
            executed=False,
            dry_run=True,
            message=(
                f"Memory is {vmem.percent:.0f}% used; {available_mb:.0f} MB available, "
                f"~{cached_mb:.0f} MB cached. To free OS caches run "
                f"'sync && echo 3 | sudo tee /proc/sys/vm/drop_caches'. SystemIQ does "
                f"not perform privileged operations automatically."
            ),
            details={
                "percent": vmem.percent,
                "available_mb": round(available_mb, 1),
                "cached_mb": round(cached_mb, 1),
            },
        )

    def _analyze_startup(self, confirm: bool, dry_run: bool) -> OptimizationResult:
        # Identify long-running, low-PID services as a proxy for startup apps.
        services: list[dict[str, object]] = []
        for proc in psutil.process_iter(["pid", "name", "create_time", "memory_percent"]):
            try:
                info = proc.info
                if info["pid"] < 1000:  # heuristic: early-started system processes
                    services.append(
                        {
                            "pid": info["pid"],
                            "name": info.get("name"),
                            "memory_percent": round(info.get("memory_percent") or 0.0, 2),
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        services.sort(key=lambda s: s["memory_percent"], reverse=True)  # type: ignore[index]
        return OptimizationResult(
            action_key="analyze_startup",
            executed=False,
            dry_run=True,
            message=f"Identified {len(services)} early/system process(es) for review.",
            details={"startup_processes": services[:20]},
        )

    def _optimize_resources(self, confirm: bool, dry_run: bool) -> OptimizationResult:
        heavy: list[dict[str, object]] = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                if (info.get("memory_percent") or 0) >= 5 or (info.get("cpu_percent") or 0) >= 20:
                    heavy.append(
                        {
                            "pid": info["pid"],
                            "name": info.get("name"),
                            "cpu_percent": round(info.get("cpu_percent") or 0.0, 2),
                            "memory_percent": round(info.get("memory_percent") or 0.0, 2),
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        heavy.sort(key=lambda s: s["memory_percent"], reverse=True)  # type: ignore[index]
        msg = (
            f"Found {len(heavy)} resource-heavy process(es). Consider closing those "
            f"you are not using to free CPU and memory."
            if heavy
            else "No resource-heavy processes detected; the system looks healthy."
        )
        return OptimizationResult(
            action_key="optimize_resources",
            executed=False,
            dry_run=True,
            message=msg,
            details={"heavy_processes": heavy[:20]},
        )


optimization_service = OptimizationService()
