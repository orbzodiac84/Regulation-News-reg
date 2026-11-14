"""Backfill press releases missed while a source was down. Dry-run by default.

Walks the agency's HTML list back to ``--since`` (KST) with conservative
pacing, then plans one action per listed article:

  INSERT  not stored yet.
  REDATE  stored with the collection time (``collected_fallback``) although
          the list shows an earlier date, so the dashboard files it under the
          wrong day. Moved to that date (``source``, KST midnight). Rows from
          the first runs after the 2026-11 MOEF/FSC source switch look like this.
  SKIP    already stored (same link), or the same title is stored within
          +/-2 days under another link (MOEF rows from the korea.kr RSS era).

Articles dated today are left to the regular collector.

Request policy (sites must never see this as abuse):
  - one list page every 4-7 s (--list-delay to slow down), single attempt,
    stop at the first error;
  - detail pages only on --apply and only for agencies with a content
    selector (FSC), each 4-7 s apart; MOEF detail pages have no body text;
  - hard caps on pages (--max-pages) and inserts (--max-inserts).

Needs the same Supabase env as the collector. Easiest: run the
"Admin - Backfill / Dedupe" workflow (.github/workflows/admin-backfill.yml).

  python scripts/admin/backfill_press.py --agency MOEF --since 2026-06-28
  python scripts/admin/backfill_press.py --agency MOEF --since 2026-06-28 --apply
  python scripts/admin/backfill_press.py --agency MOEF --since 2026-06-28 --list-delay 15,25

mofe.go.kr closed the connection on the 3rd list page at 4-7 s from a
GitHub Actions runner (2026-11-14); use a slower --list-delay there.
"""

import argparse
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.collectors import content_scraper, list_scraper, source_health  # noqa: E402
from src.collectors.date_parser import KST  # noqa: E402
from src.config.agency_codes import PublishedAtSource  # noqa: E402
from src.config.agency_loader import load_agencies  # noqa: E402
from src.db.client import get_supabase_client, select_all  # noqa: E402
from src.pipeline import build_article_row  # noqa: E402
from src.utils.logger import setup_logger  # noqa: E402

logger = setup_logger("Backfill")

LIST_DELAY_SECONDS = (4.0, 7.0)
# fetch_content sleeps 2-4 s itself; this tops it up to 4-7 s per detail page.
CONTENT_EXTRA_DELAY_SECONDS = (2.0, 3.0)
TITLE_MATCH_WINDOW_DAYS = 2


def list_config_for(agency: Dict) -> Dict:
    """Scraper config for the agency's HTML list (``list_fallback`` for RSS agencies)."""
    if agency.get('collection_method') == 'scraper':
        return agency
    fallback = agency.get('list_fallback')
    if not fallback:
        raise SystemExit(f"{agency['code']} has no HTML list (no list_fallback in agencies.json).")
    return {**agency, **fallback, 'collection_method': 'scraper'}


def normalize_title(title: str) -> str:
    return re.sub(r'\s+', '', title or '')


def kst_date(iso: str):
    return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(KST).date()


def load_existing_rows(db, agency_code: str) -> List[Dict]:
    return select_all(
        lambda: db.table('articles')
        .select('id,link,title,published_at,published_at_source')
        .eq('agency', agency_code)
        .order('id')
    )


def walk_is_complete(listed: List[Dict], problems) -> bool:
    """Any recorded problem (fetch error, page cap, empty/unreadable list) or
    zero listed rows means the walk cannot vouch that nothing is missing."""
    return bool(listed) and not problems


def plan_actions(listed: List[Dict], existing: List[Dict]) -> Dict[str, List[Tuple[Dict, Optional[Dict]]]]:
    """Pure planning step: (listed item, matching stored row) per action."""
    by_link = {row['link']: row for row in existing}
    by_title: Dict[str, List[Dict]] = {}
    for row in existing:
        by_title.setdefault(normalize_title(row.get('title')), []).append(row)

    plan: Dict[str, List[Tuple[Dict, Optional[Dict]]]] = {'INSERT': [], 'REDATE': [], 'SKIP': []}
    for item in listed:
        if item['published_at_source'] != PublishedAtSource.SOURCE.value:
            continue  # dated today: the regular collector owns it

        item_day = kst_date(item['published_at'])
        row = by_link.get(item['link'])
        if row:
            stored_day = kst_date(row['published_at'])
            if (
                row.get('published_at_source') == PublishedAtSource.COLLECTED_FALLBACK.value
                and item_day < stored_day
            ):
                plan['REDATE'].append((item, row))
            else:
                plan['SKIP'].append((item, row))
            continue

        twin = next(
            (
                r for r in by_title.get(normalize_title(item['title']), [])
                if abs((kst_date(r['published_at']) - item_day).days) <= TITLE_MATCH_WINDOW_DAYS
            ),
            None,
        )
        if twin:
            plan['SKIP'].append((item, twin))
        else:
            plan['INSERT'].append((item, None))
    return plan


def print_report(agency_code: str, since: datetime, listed: List[Dict], plan, complete: bool) -> None:
    print(f"\n=== Backfill plan: {agency_code} since {since.date()} ===")
    past = sum(1 for i in listed if i['published_at_source'] == PublishedAtSource.SOURCE.value)
    print(f"listed articles (before today): {past}")
    print(f"list walk complete: {'yes' if complete else 'NO - see source problems above; rerun after fixing'}")
    for action in ('INSERT', 'REDATE', 'SKIP'):
        print(f"{action}: {len(plan[action])}")

    inserts = [i for i, _ in plan['INSERT']]
    if inserts:
        per_month = Counter(kst_date(i['published_at']).strftime('%Y-%m') for i in inserts)
        print("INSERT per month: " + ", ".join(f"{m} {n}" for m, n in sorted(per_month.items())))
        for item in inserts:
            print(f"  + {kst_date(item['published_at'])} {item['title'][:70]}")

    for item, row in plan['REDATE']:
        print(f"  ~ {kst_date(row['published_at'])} -> {kst_date(item['published_at'])} {item['title'][:60]}")

    title_skips = [(i, r) for i, r in plan['SKIP'] if r['link'] != i['link']]
    for item, row in title_skips:
        print(f"  = title match {kst_date(item['published_at'])} {item['title'][:50]} <- {row['link'][:60]}")


def apply_plan(db, agency: Dict, plan, max_inserts: int) -> None:
    inserts = plan['INSERT']
    if len(inserts) > max_inserts:
        raise SystemExit(f"Refusing to insert {len(inserts)} rows (> --max-inserts {max_inserts}).")

    for item, row in plan['REDATE']:
        db.table('articles').update({
            'published_at': item['published_at'],
            'published_at_source': PublishedAtSource.SOURCE.value,
        }).eq('id', row['id']).execute()
    logger.info(f"Redated {len(plan['REDATE'])} rows.")

    has_content = bool((agency.get('selector') or {}).get('content'))
    saved = 0
    for item, _ in inserts:
        if has_content:
            time.sleep(random.uniform(*CONTENT_EXTRA_DELAY_SECONDS))
            item['content'] = content_scraper.fetch_content(item['link'], agency) or ''
        try:
            db.table('articles').insert(build_article_row(item)).execute()
            saved += 1
        except Exception as e:  # e.g. the collector inserted it meanwhile
            logger.warning(f"Insert skipped for {item['link']}: {e}")
    logger.info(f"Inserted {saved}/{len(inserts)} rows.")


def parse_delay(text: str) -> Tuple[float, float]:
    low, high = (float(x) for x in text.split(','))
    if not 0 < low <= high:
        raise argparse.ArgumentTypeError("--list-delay must be MIN,MAX with 0 < MIN <= MAX")
    return low, high


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--agency', required=True)
    parser.add_argument('--since', required=True, help='YYYY-MM-DD (KST)')
    parser.add_argument('--apply', action='store_true', help='write to the DB (default: dry-run)')
    parser.add_argument('--max-pages', type=int, default=80)
    parser.add_argument('--max-inserts', type=int, default=800)
    parser.add_argument('--list-delay', type=parse_delay, default=LIST_DELAY_SECONDS,
                        help='seconds between list pages, MIN,MAX (default 4,7)')
    args = parser.parse_args()

    agency = next((a for a in load_agencies() if a.get('code') == args.agency), None)
    if not agency:
        raise SystemExit(f"Unknown agency {args.agency}")
    since = KST.localize(datetime.strptime(args.since, '%Y-%m-%d'))
    if since < datetime.now(KST) - timedelta(days=400):
        raise SystemExit("--since more than ~13 months back; split the backfill.")

    db = get_supabase_client()
    existing = load_existing_rows(db, agency['code'])  # fail before touching the site

    source_health.reset()
    listed = list_scraper.fetch_list_items(
        list_config_for(agency), since=since, max_pages=args.max_pages, delay_range=args.list_delay,
    )
    problems = source_health.snapshot().get(agency['code'], [])
    for problem in problems:
        print(f"SOURCE PROBLEM: {problem.problem.value} - {problem.detail}")
    complete = walk_is_complete(listed, problems)

    plan = plan_actions(listed, existing)
    print_report(agency['code'], since, listed, plan, complete)

    if args.apply:
        apply_plan(db, agency, plan, args.max_inserts)
    else:
        print("\nDry-run: nothing written. Re-run with --apply to write.")
    return 0 if complete else 2


if __name__ == '__main__':
    sys.exit(main())
