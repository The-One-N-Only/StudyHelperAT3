import pytest

import src.search as search
import src.whitelist as whitelist


def test_result_identity_normalizes_source_name():
    first = {
        "source_name": "  WikiPEDIA\n Archive ",
        "source_id": "Record-A",
        "source_url": "https://example.test/first",
        "title": "First",
    }
    normalized = {
        "source_name": "wikipedia archive",
        "source_id": "Record-A",
        "source_url": "https://example.test/second",
        "title": "Second",
    }
    distinct_id = {**normalized, "source_id": "record-a"}

    assert search.result_identity(first) == search.result_identity(normalized)
    assert search.result_identity(first) != search.result_identity(distinct_id)


def test_canonical_source_url_normalizes_host():
    assert search.canonical_source_url(
        " HTTPS://Example.COM/Archive/Entry?view=Full#section-two "
    ) == "https://example.com/Archive/Entry?view=Full"
    assert search.canonical_source_url("javascript://example.com/archive") == ""
    assert search.canonical_source_url("/archive/entry") == ""


def test_deduplicate_results_rejects_duplicate_urls():
    first = {
        "source_name": "Wikipedia",
        "source_id": "wiki-7",
        "source_url": "https://EXAMPLE.test/shared#first",
        "title": "Shared entry",
    }
    duplicate_url = {
        "source_name": "JSTOR",
        "source_id": "jstor-99",
        "source_url": "https://example.test/shared#second",
        "title": "Provider copy",
    }

    assert search.deduplicate_results([first, duplicate_url]) == [first]


def test_deduplicate_results_preserves_first_seen_order():
    first = {
        "source_name": "Wikipedia",
        "source_id": "1",
        "source_url": "https://example.test/first",
        "title": "First",
    }
    second = {
        "source_name": "PubMed",
        "source_id": "2",
        "source_url": "https://example.test/second",
        "title": "Second",
    }
    repeated = {**first, "source_url": "https://example.test/repeated"}

    assert search.deduplicate_results([first, second, repeated]) == [first, second]


def test_whitelist_search_uses_combined_serpapi_scope(monkeypatch):
    recorded = []

    def fake_serp(query, num_results, scope, *, user_id):
        recorded.append((query, num_results, scope, user_id))
        return []

    monkeypatch.setattr(search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(search, "_search_serpapi", fake_serp)
    monkeypatch.setattr(
        whitelist,
        "get_whitelist_search_scope",
        lambda: "site:en.wikipedia.org OR site:pubmed.ncbi.nlm.nih.gov",
    )

    assert search.whitelist_search("test query", 10, user_id=1) == []
    assert recorded == [
        ("test query", 10, "site:en.wikipedia.org OR site:pubmed.ncbi.nlm.nih.gov", 1)
    ]


def test_whitelist_search_uses_serpapi_when_key_set(monkeypatch):
    monkeypatch.setattr(search, "SERP_API_KEY", "test-key")

    def fake_get(url, params=None, headers=None, timeout=None):
        assert url == "https://serpapi.com/search"
        assert params["api_key"] == "test-key"
        assert params["engine"] == "google"
        assert "site:en.wikipedia.org" in params["q"]

        class FakeResponse:
            status_code = 200
            def json(self_non):
                return {
                    "organic_results": [{
                        "link": "https://en.wikipedia.org/wiki/Test",
                        "title": "Test Title",
                        "snippet": "Test snippet"
                    }]
                }
        return FakeResponse()

    monkeypatch.setattr(search.requests, "get", fake_get)
    monkeypatch.setattr(search.whitelist, "is_allowed", lambda url: True)
    monkeypatch.setattr(search.whitelist, "get_display_name_for_domain", lambda domain: "Wikipedia")
    monkeypatch.setattr(search.whitelist, "get_domain", lambda url: "en.wikipedia.org")
    monkeypatch.setattr(search.whitelist, "get_whitelist_search_scope", lambda: "site:en.wikipedia.org")
    monkeypatch.setattr(search.db, "get_search_cache", lambda key: None)
    monkeypatch.setattr(search.db, "get_or_create_item", lambda item_data, user_id, add_to_recent_search: {"id": 0, **item_data})

    results = search.whitelist_search("test query", 1, user_id=1)

    assert len(results) == 1
    assert results[0]["source_url"] == "https://en.wikipedia.org/wiki/Test"


def test_gbooks_clamps_max_results(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        @staticmethod
        def json():
            return {"items": []}

    def fake_get(url, *, params, headers, timeout):
        captured.update(url=url, params=dict(params))
        return FakeResponse()

    monkeypatch.setattr(search.requests, "get", fake_get)
    monkeypatch.setattr(search, "GOOGLE_BOOKS_API_KEY", "")

    assert search.gbooks("archive", 500, {}, user_id=7) == []
    assert captured["url"] == "https://www.googleapis.com/books/v1/volumes"
    assert captured["params"] == {"q": "archive", "maxResults": 40}


def test_browse_routes_return_missing_serpapi_configuration(monkeypatch):
    import app as flask_app

    monkeypatch.setattr(flask_app.search, "SERP_API_KEY", "")
    expected_error = "Browse search is not configured. Add SERP_API_KEY and restart StudyLib."

    with flask_app.app.test_request_context(
        "/api/browse/search", method="POST",
        json={"query": "archive", "source": "wikipedia", "num_results": 10},
    ):
        flask_app.session["user_id"] = 4
        response, status = flask_app.browse_search()

    assert status == 503
    assert response.get_json() == {"status": False, "error": expected_error}
