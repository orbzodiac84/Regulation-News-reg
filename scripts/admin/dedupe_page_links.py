"""Delete duplicate rows created by page-dependent list links. Dry-run by default.

Before ``pagination.normalize_page_param`` existed, an article first seen on
list page 1 (``...&pageIndex=1``) and later on page N got stored a second
time as ``...&pageIndex=N`` (FSS/BOK/FSS_REG use ``pageIndex``, FSC_REG
``curPage``). On 2026-11-03 a rescan stored 19 such rows.

Rows are grouped by their page-1 form. In a group of two or more, one row
is kept - the one with a star rating, then the most views, then the page-1
link, then the oldest - and the others are deleted, so user engagement is
never dropped in favour of a bare copy. Single rows are never touched.

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
from src.db.client import get_supabase_client, select_all  # noqa: E402


def list_agency_urls() -> Dict[str, str]:
    """List-scraped, non-sanction agencies -> list URL (sanctions dedup by key)."""
    return {
        a['code']: a['url']
        for a in load_agencies()
        if a.get('collection_method') == 'scraper' and not is_sanction_agency(a['code'])
    }


def page_number(link: str, base_url: str) -> int:
    match = re.search(rf'[?&]{page_param_name(base_url)}=(\d+)(?=[&#]|$)', link)
    return int(match.group(1)) if match else 0


def keep_priority(row: Dict, canonical: str) -> Tuple:
    """Sort key; the smallest is kept."""
    return (
        -(row.get('star_rating') or 0),
        -(row.get('view_count') or 0),
        row['link'] != canonical,
        str(row.get('created_at') or ''),
        str(row['id']),
    )


def find_page_link_duplicates(rows: List[Dict], agency_urls: Dict[str, str]) -> List[Tuple[Dict, List[Dict]]]:
    """Return ``(kept row, rows to delete)`` per article stored more than once."""
    groups: Dict[str, List[Dict]] = {}
    for row in rows:
        base_url = agency_urls.get(row.get('agency'))
        if not base_url:
            continue
        canonical = normalize_page_param(row['link'], base_url, page_number(row['link'], base_url))
        groups.setdefault(canonical, []).append(row)

    result = []
    for canonical, group in groups.items():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda r: keep_priority(r, canonical))
        result.append((ordered[0], ordered[1:]))
    return result


def load_rows(db, agencies: List[str]) -> List[Dict]:
    return select_all(
        lambda: db.table('articles')
        .select('id,agency,title,link,created_at,view_count,star_rating')
        .in_('agency', agencies)
        .order('id')
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='delete duplicates (default: report only)')
    args = parser.parse_args()

    agency_urls = list_agency_urls()
    db = get_supabase_client()
    rows = load_rows(db, sorted(agency_urls))
    groups = find_page_link_duplicates(rows, agency_urls)
    to_delete = [row for _, extra in groups for row in extra]

    print(f"scanned {len(rows)} rows of {', '.join(sorted(agency_urls))}")
    print(f"articles stored more than once: {len(groups)}, rows to delete: {len(to_delete)}")
    for kept, extra in groups:
        print(f"  [{kept['agency']}] {kept['title'][:50]}")
        print(f"     keep   id={kept['id']} views={kept.get('view_count')} stars={kept.get('star_rating')} {kept['link'][-40:]}")
        for row in extra:
            print(f"     delete id={row['id']} views={row.get('view_count')} stars={row.get('star_rating')} {row['link'][-40:]}")

    if not args.apply:
        print("\nDry-run: nothing deleted. Re-run with --apply to delete.")
        return 0
    failed = 0
    for row in to_delete:
        try:
            db.table('articles').delete().eq('id', row['id']).execute()
        except Exception as e:  # e.g. a referencing row; keep going, report at the end
            failed += 1
            print(f"  ! delete failed id={row['id']}: {e}")
    print(f"Deleted {len(to_delete) - failed}/{len(to_delete)} rows.")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
