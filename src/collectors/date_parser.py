"""Date parsing helpers for scraper modules (KST-aware)."""

import re
from datetime import datetime, time
from typing import Optional, Tuple

import pytz

from src.config.agency_codes import PublishedAtSource


KST = pytz.timezone('Asia/Seoul')

TIME_RE = re.compile(r'(?<!\d)([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?')


def has_specific_time(date_str: str) -> bool:
    """Return True when the source string includes a non-midnight time."""
    if not date_str:
        return False

    match = TIME_RE.search(date_str)
    if not match:
        return False

    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3) or 0)
    return any((hour, minute, second))


def start_of_kst_day(dt: datetime) -> datetime:
    """Return KST midnight of the KST calendar day ``dt`` falls on."""
    return KST.localize(datetime.combine(dt.astimezone(KST).date(), time.min))


def resolve_published_at(
    pub_date: Optional[datetime],
    date_str: str,
    now_kst: datetime,
) -> Tuple[datetime, PublishedAtSource]:
    """Decide the ``published_at`` value to store and how to label it.

    - The source carries a real (non-midnight) time: store it as ``source``.
    - The source gives only a date and that date is before today (KST):
      store KST midnight of that date as ``source``. Such items are
      collected late (first run after a source switch, a backfill, or a
      back-dated posting); stamping them with the collection time would file
      them under the wrong day on the dashboard.
    - Otherwise (date-only for today or later, or no parseable date): store
      the collection time as ``collected_fallback``.

    Not used for sanction notices: their list date is the sanction action
    date, which usually precedes the posting by weeks.
    """
    if pub_date and has_specific_time(date_str):
        return pub_date, PublishedAtSource.SOURCE
    if pub_date and pub_date.astimezone(KST).date() < now_kst.astimezone(KST).date():
        return start_of_kst_day(pub_date), PublishedAtSource.SOURCE
    return now_kst, PublishedAtSource.COLLECTED_FALLBACK


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse various date string formats and localize to KST.

    Supported formats:
        - YYYYMMDD (no separator, used by FSS sanction notices)
        - YYYY-MM-DD or YYYY.MM.DD
    """
    if not date_str:
        return None

    try:
        # Try format: YYYYMMDD (no separator, used by FSS sanction notices)
        match_no_sep = re.search(r'^(\d{8})$', date_str.strip())
        if match_no_sep:
            dt = datetime.strptime(match_no_sep.group(1), '%Y%m%d')
            return KST.localize(dt)

        # Try format: YYYY-MM-DD or YYYY.MM.DD
        match = re.search(r'(\d{4}[.-]\d{2}[.-]\d{2})', date_str)

        if match:
            clean_date_str = match.group(1).replace('.', '-')
        else:
            clean_date_str = date_str.strip().replace('.', '-')

        dt = datetime.strptime(clean_date_str, '%Y-%m-%d')
        return KST.localize(dt)

    except ValueError:
        return None
