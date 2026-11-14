"""Pagination URL builders for list scraping."""

import re


def page_param_name(base_url: str) -> str:
    """FSC uses `curPage`, other agencies use `pageIndex`."""
    return "curPage" if "fsc.go.kr" in base_url else "pageIndex"


def build_page_url(base_url: str, page: int) -> str:
    """Build the URL for a given page number."""
    name = page_param_name(base_url)
    page_param = f"{name}={page}"
    if f"{name}=" in base_url:
        return re.sub(rf'{name}=\d+', page_param, base_url)
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}{page_param}"


def normalize_page_param(link: str, base_url: str, page: int) -> str:
    """Rewrite the list page number echoed into a detail link back to ``1``.

    FSS, BOK, FSS_REG and FSC_REG copy the current list page into every
    detail link (``...&pageIndex=2``). Without this, an article that slides
    from page 1 to page 2 gets a different link and defeats link-based dedup
    (2026-11-03: a 7-day rescan stored 19 duplicate FSS/BOK rows this way).
    Page 1 is always requested with an explicit ``=1`` (see
    ``build_page_url``), so stored links carry ``=1``.
    """
    if page <= 1:
        return link
    name = page_param_name(base_url)
    return re.sub(rf'([?&]){name}={page}(?=[&#]|$)', rf'\g<1>{name}=1', link)
