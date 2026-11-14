"""Planning logic of scripts/admin/backfill_press.py (no network, no DB)."""

import importlib.util
import os

import pytest

_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "admin", "backfill_press.py")
_spec = importlib.util.spec_from_file_location("backfill_press", _PATH)
backfill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backfill)

MOEF_LINK = (
    "https://www.mofe.go.kr/nw/nes/detailNesDtaView.do"
    "?searchBbsId=MOSFBBS_000000000028&menuNo=4010100&searchNttId={}"
)


def _listed(ntt, title, day, source="source"):
    return {
        "agency": "MOEF", "title": title, "link": MOEF_LINK.format(ntt),
        "published_at": f"{day}T00:00:00+09:00", "published_at_source": source,
    }


def _row(link, title, published_at, source):
    return {"id": hash(link) % 10_000, "link": link, "title": title,
            "published_at": published_at, "published_at_source": source}


def test_unstored_article_is_inserted():
    plan = backfill.plan_actions([_listed("MOSF_1", "새 보도자료", "2026-08-03")], [])
    assert [i["title"] for i, _ in plan["INSERT"]] == ["새 보도자료"]


def test_row_stamped_with_a_later_collection_time_is_redated():
    """First MOEF run after the switch (2026-11-10) stamped 10/28 articles '11/10'."""
    stored = _row(MOEF_LINK.format("MOSF_2"), "t", "2026-11-10T02:30:52+00:00", "collected_fallback")
    plan = backfill.plan_actions([_listed("MOSF_2", "t", "2026-10-28")], [stored])
    assert [r["id"] for _, r in plan["REDATE"]] == [stored["id"]]
    assert plan["INSERT"] == []


def test_row_with_a_source_time_is_left_alone():
    stored = _row(MOEF_LINK.format("MOSF_3"), "t", "2026-11-06T06:14:55+00:00", "source")
    plan = backfill.plan_actions([_listed("MOSF_3", "t", "2026-11-06")], [stored])
    assert plan["REDATE"] == [] and len(plan["SKIP"]) == 1


def test_same_title_from_the_korea_kr_era_is_not_inserted_twice():
    stored = _row("https://www.korea.kr/briefing/pressReleaseView.do?newsId=1",
                  "7월 1일 경제 동향", "2026-07-01T09:10:00+09:00", "collected_fallback")
    plan = backfill.plan_actions([_listed("MOSF_4", "7월  1일 경제 동향", "2026-07-01")], [stored])
    assert plan["INSERT"] == [] and len(plan["SKIP"]) == 1


def test_same_title_far_apart_is_a_different_article():
    stored = _row("https://www.korea.kr/x", "주간 경제동향", "2026-07-01T09:10:00+09:00", "source")
    plan = backfill.plan_actions([_listed("MOSF_5", "주간 경제동향", "2026-08-12")], [stored])
    assert len(plan["INSERT"]) == 1


def test_articles_dated_today_are_left_to_the_collector():
    plan = backfill.plan_actions([_listed("MOSF_6", "오늘", "2026-11-14", source="collected_fallback")], [])
    assert all(not v for v in plan.values())


def test_rss_agency_without_html_list_is_rejected():
    with pytest.raises(SystemExit):
        backfill.list_config_for({"code": "MAFRA", "collection_method": "rss"})


def test_moef_list_config_merges_the_fallback_block():
    moef = next(a for a in backfill.load_agencies() if a["code"] == "MOEF")
    cfg = backfill.list_config_for(moef)
    assert cfg["collection_method"] == "scraper"
    assert cfg["url"].startswith("https://www.mofe.go.kr/nw/nes/nesdta.do")
    assert "content" not in cfg["selector"]  # MOEF detail pages have no body text


def test_walk_with_any_problem_or_no_rows_is_incomplete():
    from src.collectors.source_health import SourceIssue, SourceProblem

    row = [_listed("MOSF_7", "t", "2026-08-01")]
    assert backfill.walk_is_complete(row, []) is True
    # Selector stopped matching: 0 rows must not read as "nothing missing".
    assert backfill.walk_is_complete([], []) is False
    assert backfill.walk_is_complete(row, [SourceIssue(SourceProblem.EMPTY, "x")]) is False
    assert backfill.walk_is_complete(row, [SourceIssue(SourceProblem.FETCH_ERROR, "503")]) is False


def test_list_delay_parsing():
    import argparse

    assert backfill.parse_delay("15,25") == (15.0, 25.0)
    for bad in ("0,5", "9,3"):
        with pytest.raises(argparse.ArgumentTypeError):
            backfill.parse_delay(bad)
