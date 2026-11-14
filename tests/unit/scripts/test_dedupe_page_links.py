"""scripts/admin/dedupe_page_links.py: only delete rows whose page-1 twin exists."""

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


def _row(i, agency, link):
    return {"id": i, "agency": agency, "title": f"t{i}", "link": link}


def test_page_n_row_with_stored_twin_is_a_duplicate():
    rows = [_row(1, "BOK", BOK.format(7, 1)), _row(2, "BOK", BOK.format(7, 3))]
    dups, orphans = dedupe.find_page_link_duplicates(rows, URLS)
    assert [r["id"] for r in dups] == [2] and orphans == []


def test_page_n_row_without_twin_is_kept():
    dups, orphans = dedupe.find_page_link_duplicates([_row(3, "BOK", BOK.format(8, 2))], URLS)
    assert dups == [] and [r["id"] for r in orphans] == [3]


def test_fsc_board_curpage_links():
    base = "https://www.fsc.go.kr/po040301/view?noticeId=4188&curPage={}&srchKey="
    rows = [_row(4, "FSC_REG", base.format(1)), _row(5, "FSC_REG", base.format(2))]
    dups, _ = dedupe.find_page_link_duplicates(rows, URLS)
    assert [r["id"] for r in dups] == [5]


def test_page_one_and_other_agencies_are_ignored():
    rows = [_row(6, "BOK", BOK.format(9, 1)), _row(7, "MOEF", "https://x/?pageIndex=2")]
    assert dedupe.find_page_link_duplicates(rows, URLS) == ([], [])


def test_sanction_agencies_are_not_scanned():
    assert not any(code.startswith("FSS_SANCTION") or code == "FSS_MGMT_NOTICE" for code in dedupe.list_agency_urls())
