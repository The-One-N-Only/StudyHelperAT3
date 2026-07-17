import pytest

import src.search as search
import src.whitelist as whitelist


def test_whitelist_search_calls_per_domain(monkeypatch):
    recorded = []

    def fake_search_site(query, num_results, domain, *, user_id):
        recorded.append((query, num_results, domain, user_id))
        return [{
            "title": f"Result from {domain}",
            "description": "Test description",
            "thumb_url": "",
            "thumb_mime": "image/jpeg",
            "thumb_height": 0,
            "source_url": f"https://{domain}/result",
            "source_name": domain,
            "source_id": f"https://{domain}/result"
        }]

    monkeypatch.setattr(search, "_search_whitelist_site", fake_search_site)
    monkeypatch.setattr(whitelist, "get_whitelisted_domains", lambda: ["en.wikipedia.org", "pubmed.ncbi.nlm.nih.gov"])

    results = search.whitelist_search("test query", 1, user_id=1)

    assert len(results) == 2
    assert recorded == [
        ("test query", 1, "en.wikipedia.org", 1),
        ("test query", 1, "pubmed.ncbi.nlm.nih.gov", 1)
    ]


def test_whitelist_search_respects_domains_argument(monkeypatch):
    called = []

    def fake_search_site(query, num_results, domain, *, user_id):
        called.append(domain)
        return []

    monkeypatch.setattr(search, "_search_whitelist_site", fake_search_site)

    search.whitelist_search("example", 1, domains=["books.google.com"], user_id=2)

    assert called == ["books.google.com"]


def test_whitelist_search_uses_serpapi_when_key_set(monkeypatch):
    monkeypatch.setattr(search, "SERP_API_KEY", "test-key")

    called = []
    def fake_get(url, params=None, headers=None, timeout=None):
        assert url == "https://serpapi.com/search"
        assert params["api_key"] == "test-key"
        assert params["engine"] == "google"
        called.append(params)

        class FakeResponse:
            status_code = 200
            def json(self_non):
                domain = None
                if 'site:' in params["q"]:
                    domain = params["q"].split('site:')[-1].split(')')[0].strip().split()[0]
                return {
                    "organic_results": [
                        {
                            "link": f"https://{domain}/test" if domain else "https://en.wikipedia.org/wiki/Test",
                            "title": "Test Title",
                            "snippet": "Test snippet"
                        }
                    ]
                }
        return FakeResponse()

    monkeypatch.setattr(search.requests, "get", fake_get)
    monkeypatch.setattr(search.whitelist, "is_allowed", lambda url: True)
    monkeypatch.setattr(search.whitelist, "get_display_name_for_domain", lambda domain: "Wikipedia")
    monkeypatch.setattr(search.whitelist, "get_domain", lambda url: "en.wikipedia.org")
    monkeypatch.setattr(search.db, "get_item_by_source", lambda source_name, source_id, user_id, add_to_recent_search: None)
    monkeypatch.setattr(search.db, "create_item", lambda item_data, user_id, add_to_recent_search: item_data)
    monkeypatch.setattr(search.whitelist, "get_whitelisted_domains", lambda: ["en.wikipedia.org", "pubmed.ncbi.nlm.nih.gov"])

    results = search.whitelist_search("test query", 1, user_id=1)

    assert len(results) == 2
    assert called[0]["q"].startswith("test query")
    assert "site:en.wikipedia.org" in called[0]["q"]
    assert "site:pubmed.ncbi.nlm.nih.gov" in called[1]["q"]
    assert results[0]["source_url"] == "https://en.wikipedia.org/test"
    assert results[1]["source_url"] == "https://pubmed.ncbi.nlm.nih.gov/test"
