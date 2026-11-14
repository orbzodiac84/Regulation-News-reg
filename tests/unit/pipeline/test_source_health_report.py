"""Pipeline-level source health: fail-closed dedup, RSS window check, digest.

Self-contained fakes (same convention as ``test_run.py``).
"""

from datetime import datetime
from types import SimpleNamespace
from typing import Dict, List

import pytest

from src import pipeline as pipeline_module
from src.collectors import source_health
from src.collectors.date_parser import KST
from src.collectors.source_health import SourceProblem
from src.pipeline import DedupStateUnavailable, Pipeline


class _Query:
    def __init__(self, db):
        self._db = db
        self._range = None
        self._cols = None

    def select(self, cols):
        self._cols = cols
        return self

    def eq(self, *_):
        return self

    def order(self, *_, **__):
        return self

    def limit(self, *_):
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def insert(self, payload):
        self._db.inserted.append(payload)
        return self

    def execute(self):
        if self._db.fail_reads and self._cols is not None:
            raise RuntimeError("{'message': 'JSON could not be generated', 'code': 400}")
        if self._cols == "link" and (self._range is None or self._range[0] == 0):
            return SimpleNamespace(data=[{"link": l} for l in self._db.links])
        return SimpleNamespace(data=[])


class FakeDB:
    def __init__(self, links=(), fail_reads=False):
        self.links = list(links)
        self.fail_reads = fail_reads
        self.inserted: List[Dict] = []

    def table(self, _name):
        return _Query(self)


class FakeScraper:
    def __init__(self):
        self.list_calls = 0

    def fetch_list_items(self, agency, last_crawled_date=None):
        self.list_calls += 1
        return []

    def fetch_content(self, link, agency_config):
        return ""

    def fetch_sanction_items(self, agency):
        return []


class FakeNotifier:
    enabled = True

    def __init__(self):
        self.messages: List[str] = []

    def send_message(self, message):
        self.messages.append(message)

    def format_and_send(self, *args):
        pass


@pytest.fixture(autouse=True)
def _clean_health():
    source_health.reset()
    yield
    source_health.reset()


def _pipeline(monkeypatch, db, rss_items=(), notifier=None, scraper=None, now=None):
    monkeypatch.setattr("src.pipeline.collect_all_rss", lambda: list(rss_items))
    if now is not None:
        monkeypatch.setattr(pipeline_module, "datetime", SimpleNamespace(now=lambda tz=None: now))
    return Pipeline(
        "config/agencies.json",
        analyzer=None,
        notifier=notifier or FakeNotifier(),
        db=db,
        scraper=scraper or FakeScraper(),
    )


def _rss(link, agency="MOEF"):
    return {"agency": agency, "title": link, "link": link, "published_at": "2026-11-14T09:00:00+09:00"}


def test_dedup_load_failure_aborts_before_any_collection(monkeypatch):
    """2026-11-03: an empty dedup cache made every listed article 'new'."""
    db = FakeDB(fail_reads=True)
    scraper = FakeScraper()
    rss_called = []
    p = _pipeline(monkeypatch, db, scraper=scraper)
    monkeypatch.setattr("src.pipeline.collect_all_rss", lambda: rss_called.append(1) or [])

    with pytest.raises(DedupStateUnavailable):
        p.run()

    assert db.inserted == []
    assert scraper.list_calls == 0
    assert rss_called == []


def test_rss_window_fully_new_is_flagged(monkeypatch):
    db = FakeDB(links=["https://old/1"])
    p = _pipeline(monkeypatch, db, rss_items=[_rss("https://new/1"), _rss("https://new/2")])

    p.run()

    issues = source_health.snapshot()["MOEF"]
    assert issues[0].problem is SourceProblem.WINDOW_OVERFLOW


def test_rss_window_overlapping_db_is_not_flagged(monkeypatch):
    db = FakeDB(links=["https://new/2"])
    p = _pipeline(monkeypatch, db, rss_items=[_rss("https://new/1"), _rss("https://new/2")])

    p.run()

    assert "MOEF" not in source_health.snapshot()


def test_digest_is_sent_in_the_daily_slot(monkeypatch):
    notifier = FakeNotifier()
    p = _pipeline(
        monkeypatch, FakeDB(links=["x"]), notifier=notifier,
        now=KST.localize(datetime(2026, 11, 14, 9, 0, 40)),
    )
    monkeypatch.setattr(
        "src.pipeline.collect_all_rss",
        lambda: source_health.record("MOEF", SourceProblem.FETCH_ERROR, "404") or [],
    )

    p.run()

    assert len(notifier.messages) == 1
    assert "기재부 (MOEF)" in notifier.messages[0]


def test_digest_is_not_sent_outside_the_slot(monkeypatch):
    notifier = FakeNotifier()
    p = _pipeline(
        monkeypatch, FakeDB(links=["x"]), notifier=notifier,
        now=KST.localize(datetime(2026, 11, 14, 9, 30, 5)),
    )
    monkeypatch.setattr(
        "src.pipeline.collect_all_rss",
        lambda: source_health.record("MOEF", SourceProblem.FETCH_ERROR, "404") or [],
    )

    p.run()

    assert notifier.messages == []


def test_healthy_run_sends_nothing_even_in_the_slot(monkeypatch):
    notifier = FakeNotifier()
    p = _pipeline(
        monkeypatch, FakeDB(links=["x"]), notifier=notifier,
        now=KST.localize(datetime(2026, 11, 14, 9, 0, 40)),
    )

    p.run()

    assert notifier.messages == []
