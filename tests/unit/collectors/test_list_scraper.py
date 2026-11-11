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
