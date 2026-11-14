"""Tests for list_scraper link canonicalization and the FSC press list config."""

from datetime import datetime

from src.collectors import list_scraper
from src.collectors.date_parser import KST
from src.config.agency_loader import load_agencies


class _Response:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


def _fsc_config():
    return next(a for a in load_agencies() if a["code"] == "FSC")


def _fsc_list_html(href: str, date_text: str) -> bytes:
    # Mirrors the live https://www.fsc.go.kr/no010101 markup.
    return (
        "<div class='board-list-wrap'><ul><li><div class='inner'>"
        "<div class='count'>15457</div>"
        "<div class='cont'><div class='subject'>"
        f"<a href='{href}'>FSC 보도자료</a>"
        "</div></div>"
        f"<div class='day'>{date_text}</div>"
        "</div></li></ul></div>"
    ).encode("utf-8")


def test_canonicalize_link_strips_query_when_opted_in():
    config = {"link_strip_query": True}
    link = (
        "https://www.fsc.go.kr/no010101/88074"
        "?srchCtgry=&curPage=2&srchKey=&srchText=&srchBeginDt=&srchEndDt="
    )

    assert list_scraper.canonicalize_link(link, config) == (
        "https://www.fsc.go.kr/no010101/88074"
    )


def test_canonicalize_link_keeps_query_by_default():
    link = "https://www.fsc.go.kr/po040301/view?noticeId=4187&curPage=1"

    assert list_scraper.canonicalize_link(link, {}) == link


def test_fsc_press_list_yields_canonical_links(monkeypatch):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    href = (
        "/no010101/88074"
        "?srchCtgry=&curPage=2&srchKey=&srchText=&srchBeginDt=&srchEndDt="
    )
    monkeypatch.setattr(list_scraper.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        list_scraper.http,
        "fetch",
        lambda *args, **kwargs: _Response(_fsc_list_html(href, today)),
    )

    items = list_scraper.fetch_list_items(_fsc_config())

    assert len(items) == 1
    assert items[0]["agency"] == "FSC"
    assert items[0]["title"] == "FSC 보도자료"
    # Same format as rows saved during the RSS era, so dedup stays stable.
    assert items[0]["link"] == "https://www.fsc.go.kr/no010101/88074"


# ---------------------------------------------------------------------------
# Cutoff, link resolution, pagination and source health
# ---------------------------------------------------------------------------

from datetime import timedelta  # noqa: E402

import pytest  # noqa: E402

from src.collectors import source_health  # noqa: E402
from src.collectors.source_health import SourceProblem  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_health():
    source_health.reset()
    yield
    source_health.reset()


def _generic_config(**extra):
    config = {
        "code": "FSS",
        "url": "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218",
        "collection_method": "scraper",
        "selector": {"list": "li.item", "title": "a", "date": ".date"},
    }
    config.update(extra)
    return config


def _rows_html(rows):
    body = "".join(
        f"<li class='item'><a href=\"{href}\">{title}</a><span class='date'>{date}</span></li>"
        for title, href, date in rows
    )
    return f"<ul>{body}</ul>".encode("utf-8")


def _serve(monkeypatch, pages):
    """Serve ``pages[n]`` (bytes or Exception) for list page n (1-based)."""
    requested = []

    def fake_fetch(url, **kwargs):
        requested.append(url)
        page = int(url.rsplit("=", 1)[1])
        content = pages.get(page, b"<ul></ul>")
        if isinstance(content, Exception):
            raise content
        return _Response(content)

    monkeypatch.setattr(list_scraper.time, "sleep", lambda _: None)
    monkeypatch.setattr(list_scraper.http, "fetch", fake_fetch)
    return requested


class TestComputeCutoff:
    NOW = KST.localize(datetime(2026, 11, 14, 10, 30))

    def test_incremental_cutoff_is_floored_to_start_of_kst_day(self):
        last = KST.localize(datetime(2026, 11, 13, 22, 10))
        assert list_scraper.compute_cutoff(self.NOW, last) == KST.localize(datetime(2026, 11, 12))

    def test_lookback_is_capped_at_seven_days(self):
        last = KST.localize(datetime(2026, 9, 1))
        assert list_scraper.compute_cutoff(self.NOW, last) == KST.localize(datetime(2026, 11, 7))

    def test_since_overrides_the_cap(self):
        since = KST.localize(datetime(2026, 7, 1, 13, 0))
        assert list_scraper.compute_cutoff(self.NOW, None, since) == KST.localize(datetime(2026, 7, 1))


def test_previous_day_item_posted_late_is_not_dropped(monkeypatch):
    """Last insert at 22:10 used to put the cutoff at 22:10 the day before,
    dropping date-only rows of that day that the board published late."""
    now = datetime.now(KST)
    last = now - timedelta(minutes=30)
    day_before = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    _serve(monkeypatch, {1: _rows_html([("late", "/view.do?nttId=9&pageIndex=1", day_before)])})

    items = list_scraper.fetch_list_items(_generic_config(), last_crawled_date=last)

    assert [i["title"] for i in items] == ["late"]


def test_page_two_links_match_the_page_one_form_stored_in_db(monkeypatch):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    old = (datetime.now(KST) - timedelta(days=30)).strftime("%Y-%m-%d")
    page1 = [(f"p1-{i}", f"/view.do?nttId={i}&pageIndex=1", today) for i in range(10)]
    page2 = [
        ("slid", "/fss/bbs/B0000188/view.do?nttId=100&pageIndex=2", today),
        ("old", "/view.do?nttId=101&pageIndex=2", old),
    ]
    _serve(monkeypatch, {1: _rows_html(page1), 2: _rows_html(page2)})

    items = list_scraper.fetch_list_items(_generic_config())

    slid = next(i for i in items if i["title"] == "slid")
    assert slid["link"] == "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=100&pageIndex=1"
    assert "old" not in [i["title"] for i in items]


def test_link_template_builds_detail_url_from_javascript_href(monkeypatch):
    config = _generic_config(
        code="MOEF",
        url="https://www.mofe.go.kr/nw/nes/nesdta.do?bbsId=MOSFBBS_000000000028&menuNo=4010100",
        link_id_pattern=r"fn_egov_select\('(MOSF_\d+)'\)",
        link_template=(
            "https://www.mofe.go.kr/nw/nes/detailNesDtaView.do"
            "?searchBbsId=MOSFBBS_000000000028&menuNo=4010100&searchNttId={id}"
        ),
    )
    today = datetime.now(KST).strftime("%Y.%m.%d.")
    _serve(monkeypatch, {1: _rows_html([
        ("press", "javascript:fn_egov_select('MOSF_000000000079950');", today),
        ("no id", "javascript:void(0);", today),
    ])})

    items = list_scraper.fetch_list_items(config)

    assert [i["link"] for i in items] == [
        "https://www.mofe.go.kr/nw/nes/detailNesDtaView.do"
        "?searchBbsId=MOSFBBS_000000000028&menuNo=4010100&searchNttId=MOSF_000000000079950"
    ]


def test_empty_first_page_is_reported(monkeypatch):
    _serve(monkeypatch, {1: b"<div>redesigned</div>"})

    assert list_scraper.fetch_list_items(_generic_config()) == []
    assert source_health.snapshot()["FSS"][0].problem is SourceProblem.EMPTY


def test_fetch_error_is_reported(monkeypatch):
    _serve(monkeypatch, {1: RuntimeError("503 Server Error")})

    assert list_scraper.fetch_list_items(_generic_config()) == []
    issue = source_health.snapshot()["FSS"][0]
    assert issue.problem is SourceProblem.FETCH_ERROR
    assert "503" in issue.detail


def test_page_cap_before_cutoff_is_reported_as_overflow(monkeypatch):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    full_page = _rows_html([(f"t{i}", f"/view.do?nttId={i}", today) for i in range(10)])
    requested = _serve(monkeypatch, {1: full_page, 2: full_page})

    list_scraper.fetch_list_items(_generic_config(), max_pages=2)

    assert len(requested) == 2
    assert source_health.snapshot()["FSS"][0].problem is SourceProblem.WINDOW_OVERFLOW


def test_reaching_cutoff_is_not_an_overflow(monkeypatch):
    old = (datetime.now(KST) - timedelta(days=30)).strftime("%Y-%m-%d")
    _serve(monkeypatch, {1: _rows_html([(f"t{i}", f"/view.do?nttId={i}", old) for i in range(10)])})

    list_scraper.fetch_list_items(_generic_config(), max_pages=1)

    assert source_health.snapshot() == {}


def test_rows_without_resolvable_links_are_reported(monkeypatch):
    """MOEF renaming fn_egov_select must not look like 'no new articles'."""
    config = _generic_config(
        code="MOEF",
        link_id_pattern=r"fn_egov_select\('(MOSF_\d+)'\)",
        link_template="https://www.mofe.go.kr/view?id={id}",
    )
    today = datetime.now(KST).strftime("%Y.%m.%d.")
    _serve(monkeypatch, {1: _rows_html([(f"t{i}", f"javascript:fn_view('X{i}')", today) for i in range(5)])})

    assert list_scraper.fetch_list_items(config) == []
    assert source_health.snapshot()["MOEF"][0].problem is SourceProblem.EMPTY


def test_link_template_without_pattern_fails_loudly(monkeypatch):
    requested = _serve(monkeypatch, {})
    config = _generic_config(code="MOEF", link_template="https://x/{id}")

    assert list_scraper.fetch_list_items(config) == []
    assert requested == []
    assert source_health.snapshot()["MOEF"][0].problem is SourceProblem.EMPTY
