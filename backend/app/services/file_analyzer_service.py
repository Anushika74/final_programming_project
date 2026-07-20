"""File-system analyzer.

Walks a directory tree and identifies large files, temporary/junk files, empty
folders and duplicate files (by content hash). Produces cleanup recommendations
and an estimate of reclaimable space.

Safety: this service is **read-only**. It never deletes anything; deletion is
handled (with confirmation) by the optimization service.
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from app.schemas.insight import (
    DuplicateGroup,
    FileInfo,
    FileScanRequest,
    FileScanResult,
)

logger = logging.getLogger(__name__)

# Extensions / name patterns commonly considered temporary or junk.
_TEMP_SUFFIXES = {".tmp", ".temp", ".log", ".bak", ".old", ".cache", ".swp", ".swo", ".part"}
_TEMP_NAMES = {"thumbs.db", ".ds_store", "desktop.ini"}
_TEMP_DIRS = {"/tmp", "/var/tmp"}

# Cap the number of files hashed for duplicate detection to keep scans fast.
_MAX_HASH_BYTES = 64 * 1024  # hash only the first 64 KB for a fast fingerprint
_MAX_FILES = 200_000


def human_size(num_bytes: float) -> str:
    """Return a human-readable file size string."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


class FileAnalyzerService:
    """Read-only file-system inspection."""

    def _is_temp(self, path: Path) -> bool:
        name = path.name.lower()
        if name in _TEMP_NAMES:
            return True
        if path.suffix.lower() in _TEMP_SUFFIXES:
            return True
        return any(str(path).startswith(d) for d in _TEMP_DIRS)

    @staticmethod
    def _quick_hash(path: Path) -> str | None:
        """Hash file size + first chunk for a fast duplicate fingerprint."""
        try:
            hasher = hashlib.sha256()
            size = path.stat().st_size
            hasher.update(str(size).encode())
            with open(path, "rb") as fh:
                hasher.update(fh.read(_MAX_HASH_BYTES))
            return hasher.hexdigest()
        except (OSError, PermissionError):
            return None

    def scan(self, request: FileScanRequest) -> FileScanResult:
        root = Path(os.path.expanduser(request.path)).resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Path does not exist or is not a directory: {root}")

        min_large_bytes = int(request.min_large_file_mb * 1024 * 1024)
        scanned = 0
        total_size = 0
        large_files: list[FileInfo] = []
        temp_files: list[FileInfo] = []
        empty_folders: list[str] = []
        size_index: dict[int, list[Path]] = {}

        root_depth = len(root.parts)
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _e: None):
            current = Path(dirpath)
            if request.max_depth is not None:
                if len(current.parts) - root_depth > request.max_depth:
                    dirnames[:] = []  # prune deeper traversal
                    continue

            if not dirnames and not filenames:
                empty_folders.append(str(current))

            for filename in filenames:
                if scanned >= _MAX_FILES:
                    break
                fpath = current / filename
                try:
                    stat = fpath.stat()
                except (OSError, PermissionError):
                    continue
                if not fpath.is_file():
                    continue

                scanned += 1
                size = stat.st_size
                total_size += size

                if size >= min_large_bytes:
                    large_files.append(
                        FileInfo(path=str(fpath), size_bytes=size, size_human=human_size(size))
                    )
                if self._is_temp(fpath):
                    temp_files.append(
                        FileInfo(path=str(fpath), size_bytes=size, size_human=human_size(size))
                    )
                if request.find_duplicates and size > 0:
                    size_index.setdefault(size, []).append(fpath)

        duplicate_groups = (
            self._find_duplicates(size_index) if request.find_duplicates else []
        )

        large_files.sort(key=lambda f: f.size_bytes, reverse=True)
        temp_files.sort(key=lambda f: f.size_bytes, reverse=True)

        reclaimable = (
            sum(f.size_bytes for f in temp_files)
            + sum(g.wasted_bytes for g in duplicate_groups)
        )

        recommendations = self._recommend(
            large_files, temp_files, empty_folders, duplicate_groups, reclaimable
        )

        return FileScanResult(
            root=str(root),
            scanned_files=scanned,
            total_size_bytes=total_size,
            large_files=large_files[:50],
            temp_files=temp_files[:50],
            empty_folders=empty_folders[:50],
            duplicate_groups=duplicate_groups[:50],
            reclaimable_bytes=reclaimable,
            recommendations=recommendations,
        )

    def _find_duplicates(self, size_index: dict[int, list[Path]]) -> list[DuplicateGroup]:
        """Hash only files that share a size (the only ones that can be dupes)."""
        groups: list[DuplicateGroup] = []
        for size, paths in size_index.items():
            if len(paths) < 2:
                continue
            by_hash: dict[str, list[Path]] = {}
            for p in paths:
                digest = self._quick_hash(p)
                if digest is None:
                    continue
                by_hash.setdefault(digest, []).append(p)
            for digest, dupes in by_hash.items():
                if len(dupes) < 2:
                    continue
                wasted = size * (len(dupes) - 1)
                groups.append(
                    DuplicateGroup(
                        hash=digest,
                        size_bytes=size,
                        files=[str(p) for p in dupes],
                        wasted_bytes=wasted,
                    )
                )
        groups.sort(key=lambda g: g.wasted_bytes, reverse=True)
        return groups

    def _recommend(
        self,
        large_files: list[FileInfo],
        temp_files: list[FileInfo],
        empty_folders: list[str],
        duplicate_groups: list[DuplicateGroup],
        reclaimable: int,
    ) -> list[str]:
        recs: list[str] = []
        if temp_files:
            recs.append(
                f"Found {len(temp_files)} temporary/junk file(s) "
                f"({human_size(sum(f.size_bytes for f in temp_files))}). Safe to remove."
            )
        if duplicate_groups:
            wasted = sum(g.wasted_bytes for g in duplicate_groups)
            recs.append(
                f"Found {len(duplicate_groups)} group(s) of duplicate files wasting "
                f"{human_size(wasted)}. Keep one copy and delete the rest."
            )
        if large_files:
            recs.append(
                f"Largest file is {large_files[0].size_human} "
                f"({large_files[0].path}). Review large files for archival."
            )
        if empty_folders:
            recs.append(f"Found {len(empty_folders)} empty folder(s) that can be removed.")
        if reclaimable:
            recs.append(f"Estimated reclaimable space: {human_size(reclaimable)}.")
        if not recs:
            recs.append("No obvious cleanup opportunities found. Nice and tidy!")
        return recs


file_analyzer_service = FileAnalyzerService()
