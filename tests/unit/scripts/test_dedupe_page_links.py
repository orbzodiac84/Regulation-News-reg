"""scripts/admin/dedupe_page_links.py: group page-N copies, never drop engagement."""

import importlib.util
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "admin", "dedupe_page_links.py")
_spec = importlib.util.spec_from_file_location("dedupe_page_links", _PATH)
dedupe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dedupe)

URLS = {
    "BOK": "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1",
    "FSC_REG": "https://www.fsc.go.kr/po040301",
}
BOK = "https://www.bok.or.kr/portal/bbs/P0000561/view.do?nttId={}&depth=201150&pageUnit=10&pageIndex={}&programType=newsData"


def _row(i, agency, link, views=0, stars=None, created="2026-11-01T00:00:00"):
    return {"id": i, "agency": agency, "title": f"t{i}", "link": link,
            "view_count": views, "star_rating": stars, "created_at": created}


def _ids(groups):
    return [(kept["id"], [r["id"] for r in extra]) for kept, extra in groups]


def test_page_n_copy_of_a_page_one_row_is_deleted():
    rows = [_row(1, "BOK", BOK.format(7, 1)), _row(2, "BOK", BOK.format(7, 3))]
    assert _ids(dedupe.find_page_link_duplicates(rows, URLS)) == [(1, [2])]


def test_starred_copy_is_kept_even_if_it_is_the_page_n_link():
    rows = [_row(1, "BOK", BOK.format(7, 1)), _row(2, "BOK", BOK.format(7, 2), stars=5)]
    assert _ids(dedupe.find_page_link_duplicates(rows, URLS)) == [(2, [1])]


def test_more_viewed_copy_is_kept():
    rows = [_row(1, "BOK", BOK.format(7, 1), views=0), _row(2, "BOK", BOK.format(7, 2), views=3)]
    assert _ids(dedupe.find_page_link_duplicates(rows, URLS)) == [(2, [1])]


def test_page_n_copies_without_a_page_one_row_are_still_deduped():
    rows = [
        _row(3, "BOK", BOK.format(8, 3), created="2026-11-03T15:10:00"),
        _row(4, "BOK", BOK.format(8, 2), created="2026-11-01T09:00:00"),
    ]
    assert _ids(dedupe.find_page_link_duplicates(rows, URLS)) == [(4, [3])]


def test_single_rows_are_never_touched():
    rows = [_row(5, "BOK", BOK.format(9, 2)), _row(6, "BOK", BOK.format(10, 1))]
    assert dedupe.find_page_link_duplicates(rows, URLS) == []


def test_fsc_board_curpage_links():
    base = "https://www.fsc.go.kr/po040301/view?noticeId=4188&curPage={}&srchKey="
    rows = [_row(7, "FSC_REG", base.format(1)), _row(8, "FSC_REG", base.format(2))]
    assert _ids(dedupe.find_page_link_duplicates(rows, URLS)) == [(7, [8])]


def test_other_agencies_are_ignored():
    rows = [_row(9, "MOEF", "https://x/?pageIndex=2"), _row(10, "MOEF", "https://x/?pageIndex=1")]
    assert dedupe.find_page_link_duplicates(rows, URLS) == []


def test_sanction_agencies_are_not_scanned():
    assert not {"FSS_SANCTION", "FSS_MGMT_NOTICE"} & set(dedupe.list_agency_urls())
