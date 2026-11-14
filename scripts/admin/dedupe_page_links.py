"""Delete duplicate rows created by page-dependent list links. Dry-run by default.

Before ``pagination.normalize_page_param`` existed, an article first seen on
list page 1 (``...&pageIndex=1``) and later on page N got stored a second
time as ``...&pageIndex=N`` (FSS/BOK/FSS_REG use ``pageIndex``, FSC_REG
``curPage``). On 2026-11-03 a rescan stored 19 such rows.

A row is deleted only when its page-1 twin is stored. Rows without a twin
are the only copy of that article and are reported but kept.

  python scripts/admin/dedupe_page_links.py           # report
  python scripts/admin/dedupe_page_links.py --apply   # delete
"""

import argparse
import os
import re
import sys
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.collectors.pagination import normalize_page_param, page_param_name  # noqa: E402
from src.config.agency_loader import is_sanction_agency, load_agencies  # noqa: E402
from src.db.client import get_supabase_client  # noqa: E402

DB_PAGE_SIZE = 1000  # PostgREST max-rows (CLAUDE.md T2)


def list_agency_urls() -> Dict[str, str]:
    """List-scraped, non-sanction agencies -> list URL (sanctions dedup by key)."""
    return {
        a['code']: a['url']
        for a in load_agencies()
        if a.get('collection_method') == 'scraper' and not is_sanction_agency(a['code'])
    }


def find_page_link_duplicates(rows: List[Dict], agency_urls: Dict[str, str]) -> Tuple[List[Dict], List[Dict]]:
    """Return (rows whose page-1 twin is stored, rows with a page>1 link but no twin)."""
    links = {row['link'] for row in rows}
    duplicates, orphans = [], []
    for row in rows:
        base_url = agency_urls.get(row.get('agency'))
        if not base_url:
            continue
        match = re.search(rf'[?&]{page_param_name(base_url)}=(\d+)(?=[&#]|$)', row['link'])
        if not match or int(match.group(1)) <= 1:
            continue
        twin = normalize_page_param(row['link'], base_url, int(match.group(1)))
        (duplicates if twin in links else orphans).append({**row, 'twin': twin})
    return duplicates, orphans


def load_rows(db, agencies: List[str]) -> List[Dict]:
    rows: List[Dict] = []
    start = 0
    while True:
        batch = (
            db.table('articles')
            .select('id,agency,title,link,created_at,view_count,star_rating')
            .in_('agency', agencies)
            .order('id')
            .range(start, start + DB_PAGE_SIZE - 1)
            .execute()
        ).data or []
        rows.extend(batch)
        if len(batch) < DB_PAGE_SIZE:
            return rows
        start += DB_PAGE_SIZE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='delete duplicates (default: report only)')
    args = parser.parse_args()

    agency_urls = list_agency_urls()
    db = get_supabase_client()
    rows = load_rows(db, sorted(agency_urls))
    duplicates, orphans = find_page_link_duplicates(rows, agency_urls)

    print(f"scanned {len(rows)} rows of {', '.join(sorted(agency_urls))}")
    print(f"duplicates (page-1 twin stored): {len(duplicates)}")
    for row in duplicates:
        print(f"  - [{row['agency']}] id={row['id']} created={row['created_at'][:16]} "
              f"views={row.get('view_count')} stars={row.get('star_rating')} {row['title'][:50]}")
    print(f"page>1 links without a twin (kept): {len(orphans)}")
    for row in orphans:
        print(f"  ? [{row['agency']}] id={row['id']} {row['title'][:50]}")

    if not args.apply:
        print("\nDry-run: nothing deleted. Re-run with --apply to delete the duplicates.")
        return 0
    for row in duplicates:
        db.table('articles').delete().eq('id', row['id']).execute()
    print(f"Deleted {len(duplicates)} rows.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
