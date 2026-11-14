"""Snapshot tests for `src.collectors.pagination.build_page_url`."""

from src.collectors.pagination import build_page_url, normalize_page_param


class TestBuildPageUrl:
    def test_fsc_uses_curpage_param(self):
        url = build_page_url("https://www.fsc.go.kr/no010101", 1)
        assert url == "https://www.fsc.go.kr/no010101?curPage=1"

    def test_fsc_replaces_existing_curpage(self):
        url = build_page_url("https://www.fsc.go.kr/no010101?curPage=1&foo=bar", 5)
        assert "curPage=5" in url
        assert "curPage=1" not in url
        assert "foo=bar" in url

    def test_non_fsc_uses_pageindex(self):
        url = build_page_url("https://www.fss.or.kr/list.do", 1)
        assert url == "https://www.fss.or.kr/list.do?pageIndex=1"

    def test_non_fsc_appends_with_existing_query(self):
        url = build_page_url("https://www.fss.or.kr/list.do?cat=a", 3)
        assert url == "https://www.fss.or.kr/list.do?cat=a&pageIndex=3"

    def test_non_fsc_replaces_existing_pageindex(self):
        url = build_page_url("https://www.fss.or.kr/list.do?pageIndex=1&foo=bar", 7)
        assert "pageIndex=7" in url
        assert "pageIndex=1" not in url
        assert "foo=bar" in url


class TestNormalizePageParam:
    def test_page_one_links_are_untouched(self):
        link = "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=1&menuNo=200218&pageIndex=1"
        assert normalize_page_param(link, "https://www.fss.or.kr/list.do", 1) == link

    def test_fss_page_two_link_maps_to_stored_page_one_form(self):
        link = "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=1&menuNo=200218&pageIndex=2"
        assert normalize_page_param(link, "https://www.fss.or.kr/list.do", 2) == (
            "https://www.fss.or.kr/fss/bbs/B0000188/view.do?nttId=1&menuNo=200218&pageIndex=1"
        )

    def test_bok_keeps_other_params_and_only_rewrites_current_page(self):
        link = (
            "https://www.bok.or.kr/portal/bbs/P0000561/view.do?nttId=11066158"
            "&pageUnit=10&pageIndex=3&programType=newsData"
        )
        out = normalize_page_param(link, "https://www.bok.or.kr/list.do?pageIndex=1", 3)
        assert "pageIndex=1&programType=newsData" in out
        assert "pageUnit=10" in out

    def test_fsc_board_uses_curpage(self):
        link = "https://www.fsc.go.kr/po040301/view?noticeId=4188&curPage=2&srchKey="
        assert normalize_page_param(link, "https://www.fsc.go.kr/po040301", 2) == (
            "https://www.fsc.go.kr/po040301/view?noticeId=4188&curPage=1&srchKey="
        )

    def test_other_numeric_params_are_not_mistaken_for_the_page(self):
        link = "https://www.fss.or.kr/view.do?nttId=2&pageIndex=2"
        assert normalize_page_param(link, "https://www.fss.or.kr/list.do", 2) == (
            "https://www.fss.or.kr/view.do?nttId=2&pageIndex=1"
        )
