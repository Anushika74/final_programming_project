"""Log analyzer.

Turns raw system log lines into human-readable explanations. It classifies each
line by severity and category using keyword/pattern heuristics and produces a
plain-English summary an operator can act on. Optionally an LLM provider can be
plugged in (see nl_service) for richer summaries; this module is dependency-free.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Severity
from app.models.log import LogEntry
from app.schemas.insight import LogAnalysisSummary, LogEntryRead

logger = logging.getLogger(__name__)


@dataclass
class _Pattern:
    regex: re.Pattern[str]
    category: str
    severity: Severity
    explain: str


# Ordered from most to least severe; first match wins.
_PATTERNS: list[_Pattern] = [
    _Pattern(
        re.compile(r"\b(kernel panic|out of memory|oom-killer|segfault|fatal)\b", re.I),
        "critical",
        Severity.CRITICAL,
        "A critical failure occurred. The system or a process hit a fatal condition "
        "(e.g. ran out of memory or crashed). Immediate investigation is advised.",
    ),
    _Pattern(
        re.compile(r"\b(failed|failure|error|denied|refused|cannot|unable)\b", re.I),
        "error",
        Severity.HIGH,
        "An operation failed. A service or command could not complete — check the "
        "named component and its dependencies.",
    ),
    _Pattern(
        re.compile(r"\b(timeout|timed out|unreachable|disconnected|lost connection)\b", re.I),
        "connectivity",
        Severity.MEDIUM,
        "A connectivity or timeout issue occurred. A network resource or service "
        "did not respond in time.",
    ),
    _Pattern(
        re.compile(r"\b(authentication failure|invalid user|sudo|permission denied|unauthorized)\b", re.I),
        "security",
        Severity.HIGH,
        "A security-relevant event was logged (authentication or permission issue). "
        "Verify whether this access attempt was expected.",
    ),
    _Pattern(
        re.compile(r"\b(warn|warning|deprecated|degraded)\b", re.I),
        "warning",
        Severity.LOW,
        "A warning was raised. Not immediately harmful, but worth monitoring.",
    ),
    _Pattern(
        re.compile(r"\b(started|stopped|listening|started|reached target|systemd)\b", re.I),
        "service",
        Severity.INFO,
        "A service lifecycle event (start/stop/target reached). Informational.",
    ),
]

_DEFAULT = _Pattern(
    re.compile(r".*"),
    "info",
    Severity.INFO,
    "Informational log line with no notable issues detected.",
)


class LogAnalyzerService:
    """Classifies and explains log lines."""

    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def classify_line(self, line: str) -> _Pattern:
        for pattern in _PATTERNS:
            if pattern.regex.search(line):
                return pattern
        return _DEFAULT

    def analyze(
        self, content: str, source: str = "manual", persist: bool = True, max_lines: int = 1000
    ) -> LogAnalysisSummary:
        """Analyze multi-line log content and return an explained summary."""
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()][:max_lines]
        by_severity: dict[str, int] = {s.value: 0 for s in Severity}
        entries: list[LogEntry] = []

        for line in lines:
            pattern = self.classify_line(line)
            by_severity[pattern.severity.value] += 1
            explanation = self._explain(line, pattern)
            entry = LogEntry(
                source=source,
                raw_log=line[:2000],
                explanation=explanation,
                category=pattern.category,
                severity=pattern.severity,
            )
            entries.append(entry)

        if persist and self.db is not None and entries:
            # Only persist non-info entries to avoid noise.
            notable = [e for e in entries if e.severity != Severity.INFO]
            for entry in notable:
                self.db.add(entry)
            if notable:
                self.db.commit()
                for entry in notable:
                    self.db.refresh(entry)

        # Sort entries by severity for presentation (critical first).
        order = {s.value: i for i, s in enumerate(
            [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
        )}
        entries.sort(key=lambda e: order.get(e.severity.value, 99))

        return LogAnalysisSummary(
            total=len(entries),
            by_severity=by_severity,
            entries=[LogEntryRead.model_validate(e) for e in entries[:200]],
        )

    def _explain(self, line: str, pattern: _Pattern) -> str:
        # Extract a probable service/unit name for a friendlier message.
        unit = self._extract_unit(line)
        prefix = f"[{unit}] " if unit else ""
        return f"{prefix}{pattern.explain}"

    @staticmethod
    def _extract_unit(line: str) -> str | None:
        # Matches typical syslog "hostname service[pid]:" prefixes.
        m = re.search(r"\s([a-zA-Z0-9_.-]+)\[\d+\]:", line)
        if m:
            return m.group(1)
        m = re.search(r"\b([a-zA-Z0-9_.-]+\.service)\b", line)
        return m.group(1) if m else None

    def recent_entries(self, limit: int = 100) -> list[LogEntry]:
        if self.db is None:
            return []
        stmt = select(LogEntry).order_by(LogEntry.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))


log_analyzer_service = LogAnalyzerService()
