"""List page scraper: fetches article list items from agency pages."""

import logging
import random
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from src.config import settings
from src.config.agency_loader import get_ssl_verify
from src.collectors import http, source_health
from src.collectors.date_parser import KST, parse_date, resolve_published_at, start_of_kst_day
from src.collectors.pagination import build_page_url, normalize_page_param
from src.collectors.source_health import SourceProblem


logger = logging.getLogger(__name__)


MAX_PAGES = 15

# Regular runs never look further back than this, even if the DB was cleared
# or the collector was down longer (use scripts/admin/backfill_press.py).
MAX_LOOKBACK_DAYS = 7


def canonicalize_link(link: str, agency_config: Dict) -> str:
    """Drop query/fragment when the agency opts in via ``link_strip_query``.

    Some list pages (e.g. FSC 보도자료) append page-dependent query strings
    such as ``curPage=2`` to every detail link. The same article would then
    get a different link once it moves to page 2, defeating link-based dedup.
    """
    if not agency_config.get('link_strip_query'):
        return link
    parts = urlsplit(link)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))


def resolve_link(href: Optional[str], base_url: str, agency_config: Dict, page: int) -> Optional[str]:
    """Turn a list-row href into the canonical detail link stored in the DB.

    ``link_id_pattern`` + ``link_template`` (agencies.json) cover boards whose
    rows link via JavaScript, e.g. MOEF ``javascript:fn_egov_select('MOSF_…')``.
    Returns ``None`` when such a row carries no id.
    """
    template = agency_config.get('link_template')
    if template:
        match = re.search(agency_config['link_id_pattern'], href or '')
        return template.format(id=match.group(1)) if match else None

    if href:
        link = href if href.startswith('http') else urljoin(base_url, href)
        link = normalize_page_param(link, base_url, page)
    else:
        link = base_url
    return canonicalize_link(link, agency_config)


def compute_cutoff(
    now_kst: datetime,
    last_crawled_date: Optional[datetime],
    since: Optional[datetime] = None,
) -> datetime:
    """Oldest list date (KST midnight) a run accepts.

    Regular runs re-read one day before the newest stored item, floored to
    the start of that KST day: list pages show dates only, so a time-of-day
    cutoff would silently drop items that boards post late with the previous
    day's date (observed on MOEF). Overlap costs nothing; link dedup drops
    already stored items. ``since`` (backfill) overrides both limits.
    """
    if since is not None:
        return start_of_kst_day(since)
    floor = now_kst - timedelta(days=MAX_LOOKBACK_DAYS)
    if last_crawled_date is None:
        return start_of_kst_day(floor)
    return start_of_kst_day(max(last_crawled_date - timedelta(days=1), floor))


def fetch_list_items(
    agency_config: Dict,
    last_crawled_date: Optional[datetime] = None,
    *,
    since: Optional[datetime] = None,
    max_pages: int = MAX_PAGES,
    delay_range: Optional[Tuple[float, float]] = None,
) -> List[Dict]:
    """Fetch list of articles using HTML scraping with automatic pagination.

    Loops through pages until it hits data older than the cutoff (see
    ``compute_cutoff``). ``since``/``max_pages``/``delay_range`` exist for the
    backfill script; the pipeline uses the defaults.
    """
    if agency_config.get('collection_method') != 'scraper':
        return []

    code = agency_config.get('code')
    base_url = agency_config.get('url')
    selectors = agency_config.get('selector', {})
    list_selector = selectors.get('list')

    if not base_url or not list_selector:
        logger.error(f"[{code}] Missing URL or list selector.")
        return []

    now_kst = datetime.now(KST)

    if last_crawled_date and last_crawled_date.tzinfo is None:
        last_crawled_date = KST.localize(last_crawled_date)

    cutoff_date = compute_cutoff(now_kst, last_crawled_date, since)
    mode = 'Backfill' if since else ('Incremental' if last_crawled_date else f'Full Scan ({MAX_LOOKBACK_DAYS}d)')
    logger.info(f"[{code}] {mode}: >= {cutoff_date.strftime('%Y-%m-%d')}")

    delay_min, delay_max = delay_range or (settings.SCRAPER_RETRY_DELAY_MIN, settings.SCRAPER_RETRY_DELAY_MAX)
    category = agency_config.get('category', 'press_release')

    all_items: List[Dict] = []
    reached_cutoff = False
    page = 1

    while page <= max_pages:
        current_url = build_page_url(base_url, page)

        logger.info(f"  [{code}] Page {page} fetching...")

        try:
            time.sleep(random.uniform(delay_min, delay_max))
            response = http.fetch(current_url, verify=get_ssl_verify(code))

            soup = BeautifulSoup(response.content, 'html.parser')
            rows = soup.select(list_selector)

            if not rows:
                if page == 1:
                    logger.warning(f"[{code}] No items found on Page 1 (Selector: {list_selector})")
                    source_health.record(code, SourceProblem.EMPTY, f"list selector matched nothing: {list_selector}")
                else:
                    logger.info(f"  [{code}] Page {page} empty. Stopping.")
                break

            page_items: List[Dict] = []

            for row in rows:
                try:
                    title_sel = selectors.get('title')
                    title_elem = row.select_one(title_sel) if title_sel else row.select_one('a')

                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    link = resolve_link(title_elem.get('href'), base_url, agency_config, page)
                    if not link:
                        continue

                    date_sel = selectors.get('date')
                    date_str = ""
                    if date_sel:
                        date_elem = row.select_one(date_sel)
                        if date_elem:
                            date_str = date_elem.get_text(strip=True)

                    pub_date = parse_date(date_str)
                    if pub_date and pub_date < cutoff_date:
                        reached_cutoff = True
                        continue

                    stored_at, stored_source = resolve_published_at(pub_date, date_str, now_kst)
                    page_items.append({
                        'title': title,
                        'link': link,
                        'published_at': stored_at.isoformat(),
                        'published_at_source': stored_source.value,
                        'agency': code,
                        'category': category,
                    })

                except Exception as e:
                    logger.error(f"Error parsing row: {e}")
                    continue

            if page_items:
                all_items.extend(page_items)
                logger.info(f"    > Found {len(page_items)} items on Page {page}.")

            if reached_cutoff:
                logger.info(f"  [{code}] Reached cutoff on Page {page}. Stopping.")
                break

            if len(rows) < 3:
                break

            page += 1

        except Exception as e:
            logger.error(f"[{code}] Error fetching page {page}: {e}")
            source_health.record(code, SourceProblem.FETCH_ERROR, f"page {page}: {e}")
            break

    if page > max_pages and not reached_cutoff:
        logger.warning(f"[{code}] Page cap ({max_pages}) hit before reaching cutoff; older items may be missing.")
        source_health.record(
            code, SourceProblem.WINDOW_OVERFLOW,
            f"page cap {max_pages} hit before {cutoff_date.strftime('%Y-%m-%d')}",
        )

    return all_items
