"""Supabase client module.

Importing this module has no side effects. Environment variables are only
read when the client is actually used (method access on `supabase` or
explicit `get_supabase_client()` call). The real client is created once
and cached as a singleton.
"""

from typing import Any, Callable, Dict, List, Optional

from supabase import create_client, Client

from src.config.settings import (
    load_env,
    get_supabase_url,
    get_supabase_anon_key,
    get_supabase_service_role_key,
)

_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Return the cached Supabase client, creating it on first call."""
    global _client
    if _client is None:
        load_env()
        url = get_supabase_url()
        key = get_supabase_service_role_key() or get_supabase_anon_key()
        _client = create_client(url, key)
    return _client


class _LazySupabaseClient:
    """Lazy proxy around the real Supabase `Client`.

    Importing this object is free; the underlying client is only created
    when an attribute is accessed (e.g. `supabase.table(...)`).
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(get_supabase_client(), name)


supabase: Any = _LazySupabaseClient()


# PostgREST server-side ``max-rows`` cap (CLAUDE.md T2).
POSTGREST_MAX_ROWS = 1000


def select_all(build_query: Callable[[], Any], page_size: int = POSTGREST_MAX_ROWS) -> List[Dict]:
    """Return every row of a select, paging in ``max-rows`` windows.

    A single ``.execute()`` silently truncates at ``max-rows`` (CLAUDE.md T2).
    ``build_query`` must return a fresh query (``table(...).select(...)`` plus
    filters/order) on each call; ``.range()`` is applied here.
    """
    rows: List[Dict] = []
    start = 0
    while True:
        batch = build_query().range(start, start + page_size - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        start += page_size
