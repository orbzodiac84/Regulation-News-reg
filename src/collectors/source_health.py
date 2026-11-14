"""Per-cycle source health registry.

Collectors swallow fetch failures and return ``[]`` so one broken agency
cannot stop the cycle. That also made dead sources invisible: after the
korea.kr RSS shutdown (2026-07-01) MOEF returned 404 on every run for four
months while each run still reported success. Collectors record problems
here; ``Pipeline`` reports them at the end of each cycle (log summary and a
once-a-day Telegram digest).

Module-level state is reset by ``Pipeline.run`` at the start of each cycle.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, NamedTuple

from src.config import settings
from src.services.notifier import escape_markdown


class SourceProblem(str, Enum):
    # HTTP 4xx/5xx or connection failure (after the collector's own retries).
    FETCH_ERROR = "fetch_error"
    # Responded, but the feed had no entries or the list selector matched nothing.
    EMPTY = "empty"
    # Newest entry is older than the stale threshold (feed alive but abandoned).
    STALE = "stale"
    # The fetched window may not reach back to the last collected item, so
    # items in between could be missing (RSS window fully new, list page cap hit).
    WINDOW_OVERFLOW = "window_overflow"

    def __str__(self) -> str:  # pragma: no cover - trivial (see CLAUDE.md T3)
        return self.value


class SourceIssue(NamedTuple):
    problem: SourceProblem
    detail: str


_issues: Dict[str, List[SourceIssue]] = {}


def reset() -> None:
    _issues.clear()


def record(agency_code: str, problem: SourceProblem, detail: str) -> None:
    _issues.setdefault(str(agency_code), []).append(SourceIssue(problem, detail))


def snapshot() -> Dict[str, List[SourceIssue]]:
    return {code: list(issues) for code, issues in _issues.items()}


PROBLEM_LABELS = {
    SourceProblem.FETCH_ERROR: "응답 오류",
    SourceProblem.EMPTY: "항목 없음",
    SourceProblem.STALE: "갱신 중단",
    SourceProblem.WINDOW_OVERFLOW: "누락 가능",
}

DIGEST_DETAIL_MAX_CHARS = 160


def is_digest_slot(now_kst: datetime) -> bool:
    """Whether this run is the once-a-day digest run (see settings)."""
    return (
        now_kst.hour == settings.SOURCE_HEALTH_DIGEST_HOUR_KST
        and now_kst.minute < settings.SOURCE_HEALTH_DIGEST_WINDOW_MINUTES
    )


def format_digest(
    issues: Dict[str, List[SourceIssue]],
    agency_names: Dict[str, str],
    now_kst: datetime,
) -> str:
    """Telegram (legacy Markdown) message listing this run's source problems."""
    lines = [f"⚠️ *수집 소스 점검 필요* ({now_kst.strftime('%Y-%m-%d %H:%M')} KST)", ""]
    for code in sorted(issues):
        name = escape_markdown(agency_names.get(code, code))
        for issue in issues[code]:
            detail = issue.detail
            if len(detail) > DIGEST_DETAIL_MAX_CHARS:
                detail = detail[:DIGEST_DETAIL_MAX_CHARS] + "…"
            lines.append(f"• {name} — {PROBLEM_LABELS[issue.problem]}: {escape_markdown(detail)}")
    lines += ["", "하루 1회(09시대 실행)만 발송됩니다. 상세는 GitHub Actions 실행 로그 참고."]
    return "\n".join(lines)
