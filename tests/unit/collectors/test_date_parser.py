"""Snapshot tests for `src.collectors.date_parser.parse_date`."""

from datetime import datetime, timezone

import pytz

from src.collectors.date_parser import KST, parse_date, resolve_published_at
from src.config.agency_codes import PublishedAtSource


class TestParseDate:
    def test_parses_yyyymmdd_no_separator(self):
        result = parse_date("20240315")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15
        # Localized to KST.
        assert result.tzinfo is not None
        assert result.tzinfo.zone == KST.zone

    def test_parses_dashed_date(self):
        result = parse_date("2024-03-15")
        expected = pytz.timezone("Asia/Seoul").localize(datetime(2024, 3, 15))
        assert result == expected

    def test_parses_dotted_date(self):
        result = parse_date("2024.03.15")
        assert result is not None
        assert (result.year, result.month, result.day) == (2024, 3, 15)

    def test_returns_none_on_empty_string(self):
        assert parse_date("") is None

    def test_returns_none_on_garbage(self):
        # Unparseable input — current behavior is to swallow ValueError
        # and return None.
        assert parse_date("not-a-date") is None


class TestResolvePublishedAt:
    NOW = KST.localize(datetime(2026, 11, 14, 10, 30))

    def test_source_time_is_kept(self):
        pub = KST.localize(datetime(2026, 11, 13, 15, 14, 55))
        stored, source = resolve_published_at(pub, "2026-11-13 15:14:55.0", self.NOW)
        assert stored == pub
        assert source is PublishedAtSource.SOURCE

    def test_past_date_only_is_stored_at_kst_midnight_of_that_date(self):
        pub = KST.localize(datetime(2026, 10, 28))
        stored, source = resolve_published_at(pub, "2026.10.28.", self.NOW)
        assert stored == KST.localize(datetime(2026, 10, 28))
        assert source is PublishedAtSource.SOURCE

    def test_past_date_only_from_utc_feed_uses_its_kst_day(self):
        # "Tue, 27 Oct 2026 15:00:00 GMT" is 2026-10-28 00:00 KST.
        pub = datetime(2026, 10, 27, 15, 0, tzinfo=timezone.utc)
        stored, source = resolve_published_at(pub, "2026-10-28 00:00:00", self.NOW)
        assert stored == KST.localize(datetime(2026, 10, 28))
        assert source is PublishedAtSource.SOURCE

    def test_today_date_only_falls_back_to_collection_time(self):
        pub = KST.localize(datetime(2026, 11, 14))
        stored, source = resolve_published_at(pub, "2026-11-14", self.NOW)
        assert stored == self.NOW
        assert source is PublishedAtSource.COLLECTED_FALLBACK

    def test_future_date_only_falls_back_to_collection_time(self):
        pub = KST.localize(datetime(2026, 11, 16))
        stored, source = resolve_published_at(pub, "2026-11-16", self.NOW)
        assert stored == self.NOW
        assert source is PublishedAtSource.COLLECTED_FALLBACK

    def test_unparseable_falls_back_to_collection_time(self):
        stored, source = resolve_published_at(None, "n/a", self.NOW)
        assert stored == self.NOW
        assert source is PublishedAtSource.COLLECTED_FALLBACK
