from src.db import client as db_client


def test_get_supabase_client_prefers_service_role_key(monkeypatch):
    captured = {}
    sentinel = object()

    def fake_create_client(url, key):
        captured["url"] = url
        captured["key"] = key
        return sentinel

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setattr(db_client, "load_env", lambda: None)
    monkeypatch.setattr(db_client, "create_client", fake_create_client)
    monkeypatch.setattr(db_client, "_client", None)

    assert db_client.get_supabase_client() is sentinel
    assert captured == {
        "url": "https://test.supabase.co",
        "key": "service-role-key",
    }


def test_get_supabase_client_falls_back_to_anon_key(monkeypatch):
    captured = {}
    sentinel = object()

    def fake_create_client(url, key):
        captured["url"] = url
        captured["key"] = key
        return sentinel

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(db_client, "load_env", lambda: None)
    monkeypatch.setattr(db_client, "create_client", fake_create_client)
    monkeypatch.setattr(db_client, "_client", None)

    assert db_client.get_supabase_client() is sentinel
    assert captured == {
        "url": "https://test.supabase.co",
        "key": "anon-key",
    }


def test_select_all_pages_until_a_short_batch():
    """PostgREST truncates at max-rows (CLAUDE.md T2): keep paging."""
    from types import SimpleNamespace

    from src.db.client import select_all

    data = [{"id": i} for i in range(5)]
    ranges = []

    class Query:
        def range(self, start, end):
            ranges.append((start, end))
            self._slice = data[start:end + 1]
            return self

        def execute(self):
            return SimpleNamespace(data=self._slice)

    assert select_all(Query, page_size=2) == data
    assert ranges == [(0, 1), (2, 3), (4, 5)]
