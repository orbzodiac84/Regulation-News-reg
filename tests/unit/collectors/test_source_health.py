"""Tests for the per-cycle source health registry and its daily digest."""

from datetime import datetime

import pytest

from src.collectors import source_health
from src.collectors.date_parser import KST
from src.collectors.source_health import SourceProblem


@pytest.fixture(autouse=True)
def _clean():
    source_health.reset()
    yield
    source_health.reset()


def test_record_and_reset():
    source_health.record("MOEF", SourceProblem.FETCH_ERROR, "404")
    source_health.record("MOEF", SourceProblem.STALE, "old")

    assert [i.problem for i in source_health.snapshot()["MOEF"]] == [
        SourceProblem.FETCH_ERROR, SourceProblem.STALE,
    ]
    source_health.reset()
    assert source_health.snapshot() == {}


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [(9, 0, True), (9, 29, True), (9, 30, False), (8, 59, False), (21, 5, False)],
)
def test_digest_is_sent_only_in_the_daily_slot(hour, minute, expected):
    assert source_health.is_digest_slot(KST.localize(datetime(2026, 11, 14, hour, minute))) is expected


def test_digest_uses_agency_names_and_escapes_markdown():
    issues = {
        "FSS_REG_INFO": [source_health.SourceIssue(SourceProblem.EMPTY, "selector .bd-list matched nothing")],
        "MOEF": [source_health.SourceIssue(
            SourceProblem.FETCH_ERROR, "404 for https://www.korea.kr/rss/dept_mofe.xml",
        )],
    }
    names = {"MOEF": "기재부 (MOEF)"}

    text = source_health.format_digest(issues, names, KST.localize(datetime(2026, 11, 14, 9, 0)))

    assert "기재부 (MOEF) — 응답 오류" in text
    assert "dept\\_mofe.xml" in text
    # Falls back to the (escaped) code when the name is unknown.
    assert "FSS\\_REG\\_INFO — 항목 없음" in text


def test_long_details_are_truncated():
    issues = {"MOEF": [source_health.SourceIssue(SourceProblem.FETCH_ERROR, "x" * 1000)]}

    text = source_health.format_digest(issues, {}, KST.localize(datetime(2026, 11, 14, 9, 0)))

    assert "x" * source_health.DIGEST_DETAIL_MAX_CHARS + "…" in text
    assert "x" * (source_health.DIGEST_DETAIL_MAX_CHARS + 1) not in text
