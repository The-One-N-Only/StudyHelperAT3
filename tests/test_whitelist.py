import pytest
import src.search as search
import src.whitelist as whitelist


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def test_allowed_exact_domain():
    assert whitelist.is_allowed("https://en.wikipedia.org/wiki/Test") == True

def test_allowed_wildcard_domain():
    assert whitelist.is_allowed("https://uni.edu.au/page") == True

def test_not_allowed_domain():
    assert whitelist.is_allowed("https://example.com/page") == False

def test_malformed_url():
    assert whitelist.is_allowed("not-a-url") == False

def test_get_domain():
    assert whitelist.get_domain("https://en.wikipedia.org/wiki/Test") == "en.wikipedia.org"


def test_get_whitelist_search_scope_includes_all_exact_domains():
    scope = whitelist.get_whitelist_search_scope()
    expected_domains = whitelist.WHITELIST["domains"]
    for domain in expected_domains:
        assert f"site:{domain}" in scope


def test_whitelist_search_queries_each_whitelisted_domain(monkeypatch):
    search.GOOGLE_SEARCH_API_KEY = "fake-key"
    search.GOOGLE_SEARCH_ENGINE_ID = "fake-cx"

    calls = []

    def fake_get(url, params=None, headers=None, timeout=10):
        calls.append(params)
        return DummyResponse({"items": [{"link": "https://en.wikipedia.org/wiki/Test", "title": "Test", "snippet": "Snippet"}]})

    monkeypatch.setattr(search.requests, "get", fake_get)
    monkeypatch.setattr(search.db, "get_item_by_source", lambda *args, **kwargs: None)
    monkeypatch.setattr(search.db, "create_item", lambda item_data, *args, **kwargs: item_data)

    results = search.whitelist_search("test query", 5, user_id=1)

    assert len(results) >= 1
    assert len(calls) >= 1
    assert any("site:" in params["q"] for params in calls)


def test_whitelist_search_falls_back_to_domain_homepage(monkeypatch):
    search.GOOGLE_SEARCH_API_KEY = ""
    search.GOOGLE_SEARCH_ENGINE_ID = ""

    monkeypatch.setattr(search.requests, "get", lambda *args, **kwargs: DummyResponse("<rss />"))
    monkeypatch.setattr(search, "_search_with_bing_rss", lambda query, num_results: [])
    monkeypatch.setattr(search.db, "get_item_by_source", lambda *args, **kwargs: None)
    monkeypatch.setattr(search.db, "create_item", lambda item_data, *args, **kwargs: item_data)

    results = search.whitelist_search("test query", 3, user_id=1)

    assert results
    assert any(item["source_url"] == "https://en.wikipedia.org/" for item in results)