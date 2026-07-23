import pytest

import src.search as search
import src.whitelist as whitelist
import src.citations as citations


# ---------------------------------------------------------------------------
# Citation formatting
# ---------------------------------------------------------------------------

def test_format_apa_with_author_year():
    assert citations.format_apa("Title", "Source", "url.com", "Author", "2023") == "Author, A. (2023). Title. Source. url.com"

def test_format_apa_without_author():
    assert citations.format_apa("Title", "Source", "url.com") == "Source. (n.d.). Title. Retrieved from url.com"

def test_format_harvard_with_author_year():
    assert citations.format_harvard("Title", "Source", "url.com", "Author", "2023") == "Author (2023) 'Title', Source, available at: url.com"

def test_format_harvard_without_author():
    assert citations.format_harvard("Title", "Source", "url.com") == "Source (n.d.) 'Title', available at: url.com"


# ---------------------------------------------------------------------------
# Search result identity / dedup / canonicalisation
# ---------------------------------------------------------------------------

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
    first = {"source_name": "Wikipedia", "source_id": "wiki-7", "source_url": "https://EXAMPLE.test/shared#first", "title": "Shared entry"}
    dup = {"source_name": "JSTOR", "source_id": "jstor-99", "source_url": "https://example.test/shared#second", "title": "Provider copy"}
    assert search.deduplicate_results([first, dup]) == [first]


def test_deduplicate_results_preserves_first_seen_order():
    first = {"source_name": "Wikipedia", "source_id": "1", "source_url": "https://example.test/first", "title": "First"}
    second = {"source_name": "PubMed", "source_id": "2", "source_url": "https://example.test/second", "title": "Second"}
    repeated = {**first, "source_url": "https://example.test/repeated"}
    assert search.deduplicate_results([first, second, repeated]) == [first, second]


# ---------------------------------------------------------------------------
# Whitelist search / SerpAPI / Google Books
# ---------------------------------------------------------------------------

def test_whitelist_search_uses_combined_serpapi_scope(monkeypatch):
    recorded = []
    def fake_serp(query, num_results, scope, *, user_id):
        recorded.append((query, num_results, scope, user_id))
        return []
    monkeypatch.setattr(search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(search, "_search_serpapi", fake_serp)
    monkeypatch.setattr(whitelist, "get_whitelist_search_scope", lambda: "site:en.wikipedia.org OR site:pubmed.ncbi.nlm.nih.gov")
    assert search.whitelist_search("test query", 10, user_id=1) == []
    assert recorded == [("test query", 10, "site:en.wikipedia.org OR site:pubmed.ncbi.nlm.nih.gov", 1)]


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
                return {"organic_results": [{"link": "https://en.wikipedia.org/wiki/Test", "title": "Test Title", "snippet": "Test snippet"}]}
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


# ---------------------------------------------------------------------------
# Browse routes / 503 when unconfigured
# ---------------------------------------------------------------------------

def test_browse_routes_return_missing_serpapi_configuration(monkeypatch):
    import app as flask_app
    monkeypatch.setattr(flask_app.search, "SERP_API_KEY", "")
    expected = "Browse search is not configured. Add SERP_API_KEY and restart StudyLib."
    with flask_app.app.test_request_context("/api/browse/search", method="POST", json={"query": "archive", "source": "wikipedia", "num_results": 10}):
        flask_app.session["user_id"] = 4
        response, status = flask_app.browse_search()
    assert status == 503
    assert response.get_json() == {"status": False, "error": expected}


# ---------------------------------------------------------------------------
# Basic Flask integration (route existence)
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        with c.session_transaction() as s:
            s['user_id'] = 1
            s['username'] = 'test-user'
        yield c

def test_routes_respond_ok(client):
    assert client.get('/').status_code == 200
    assert client.get('/browse').status_code == 200


# ---------------------------------------------------------------------------
# Thumbnail URL extraction
# ---------------------------------------------------------------------------

SAFE_PASS_URLS = [
    ("serpapi_cdn", "https://serpapi.com/searches/abc123/thumbnails/xyz.jpg"),
    ("gstatic", "https://encrypted-tbn0.gstatic.com/images?q=tbn:ABC123"),
    ("googleusercontent", "https://lh3.googleusercontent.com/abc/xyz.jpg"),
    ("books_google", "https://books.google.com/books/content?id=abc&printsec=frontcover&img=1&zoom=1"),
    ("wikimedia", "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Example.jpg/200px-Example.jpg"),
    ("whitelisted_domain", "https://www.britannica.com/some-thumbnail.jpg"),
    ("wikipedia", "https://en.wikipedia.org/static/images/project-logos/enwiki.png"),
    ("pubmed", "https://pubmed.ncbi.nlm.nih.gov/favicon.ico"),
]

SAFE_REJECT_URLS = [
    ("unknown_domain", "https://some-random-site.com/image.jpg"),
    ("fragment", "https://serpapi.com/searches/abc/thumb.jpg#frag"),
    ("credentials", "https://user:pass@serpapi.com/thumb.jpg"),
    ("too_long", "https://serpapi.com/" + "x" * 300),
]


class TestSafeBrowseImageUrl:
    @pytest.mark.parametrize("_label,url", SAFE_PASS_URLS)
    def test_allowed_pass(self, _label, url):
        assert search._safe_browse_image_url(url) == url

    @pytest.mark.parametrize("_label,url", SAFE_REJECT_URLS)
    def test_rejected(self, _label, url):
        assert search._safe_browse_image_url(url) == ""

    @pytest.mark.parametrize("url", ["", None])
    def test_falsy_rejected(self, url):
        assert search._safe_browse_image_url(url) == ""

    def test_no_hostname_rejected(self):
        assert search._safe_browse_image_url("https:///path") == ""

    def test_http_upgraded_to_https(self):
        result = search._safe_browse_image_url("http://encrypted-tbn0.gstatic.com/images?q=tbn:ABC")
        assert result == "https://encrypted-tbn0.gstatic.com/images?q=tbn:ABC"

    def test_gbooks_http_upgraded(self):
        result = search._safe_browse_image_url(
            "http://books.google.com/books/content?id=abc123&printsec=frontcover&img=1&zoom=1&edge=curl&source=gbs_api"
        )
        assert "books.google.com" in result
        assert result.startswith("https://")


class TestBrowseResultImageUrl:

    @pytest.mark.parametrize("_label,item,expected", [
        ("thumbnail_field", {"link": "https://www.britannica.com/topic/something", "title": "Something", "snippet": "test", "thumbnail": "https://serpapi.com/searches/abc123/thumbnails/xyz.jpg"}, "https://serpapi.com/searches/abc123/thumbnails/xyz.jpg"),
        ("gstatic_thumbnail", {"link": "https://en.wikipedia.org/wiki/Test", "title": "Test", "snippet": "test", "thumbnail": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTest"}, "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTest"),
    ])
    def test_direct_thumbnail(self, _label, item, expected):
        assert search._browse_result_image_url(item) == expected

    @pytest.mark.parametrize("_label,item,expected", [
        ("favicon_field", {"link": "https://www.britannica.com/topic/test", "favicon": "https://www.britannica.com/favicon.ico"}, "https://www.britannica.com/favicon.ico"),
        ("favicon_no_thumbnail", {"link": "https://www.britannica.com/topic/test", "favicon": "https://www.britannica.com/favicon.ico"}, "https://www.britannica.com/favicon.ico"),
        ("empty_thumbnail_fallback", {"link": "https://www.britannica.com/topic/test", "thumbnail": "", "favicon": "https://www.britannica.com/favicon.ico"}, "https://www.britannica.com/favicon.ico"),
    ])
    def test_favicon_from_whitelisted(self, _label, item, expected):
        assert search._browse_result_image_url(item) == expected

    @pytest.mark.parametrize("_label,item,expected", [
        ("no_img_fallback", {"link": "https://www.britannica.com/topic/test"}, "https://www.britannica.com/favicon.ico"),
        ("realistic_serp", {"position": 1, "title": "Machine Learning - Wikipedia", "link": "https://en.wikipedia.org/wiki/Machine_learning", "displayed_link": "https://en.wikipedia.org \u203a wiki \u203a Machine_learning", "snippet": "...", "sitelinks": {"inline": []}, "about_this_result": {}}, "https://en.wikipedia.org/favicon.ico"),
    ])
    def test_fallback_to_link_domain(self, _label, item, expected):
        assert search._browse_result_image_url(item) == expected

    def test_thumbnail_priority_over_favicon(self):
        assert search._browse_result_image_url({"thumbnail": "https://serpapi.com/searches/thumb.jpg", "favicon": "https://www.britannica.com/favicon.ico"}) == "https://serpapi.com/searches/thumb.jpg"

    def test_non_whitelisted_favicon_rejected(self):
        assert search._browse_result_image_url({"link": "https://some-other-site.com/test", "favicon": "https://some-other-site.com/favicon.ico"}) == ""

    def test_google_books_cover_not_thumbnail(self):
        result = search._browse_result_image_url({"link": "https://books.google.com/books?id=abc123XYZ", "thumbnail": "https://serpapi.com/thumb.jpg", "favicon": "https://books.google.com/favicon.ico"})
        assert "books.google.com/books/content" in result
        assert "abc123XYZ" in result

    @pytest.mark.parametrize("_label,item,expected_contains", [
        ("cse_thumbnail", {"link": "https://www.britannica.com/topic/test", "pagemap": {"cse_thumbnail": [{"src": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTest"}]}}, "gstatic.com"),
        ("cse_image", {"link": "https://en.wikipedia.org/wiki/Test", "pagemap": {"cse_image": [{"src": "https://upload.wikimedia.org/wikipedia/en/thumb/test.jpg"}]}}, "wikimedia.org"),
    ])
    def test_pagemap_extraction(self, _label, item, expected_contains):
        assert expected_contains in search._browse_result_image_url(item)


class TestEndToEndThumbnailFlow:
    SERPAPI_JSON = {
        "search_metadata": {"status": "Success"},
        "organic_results": [
            {"position": 1, "title": "Test - Britannica", "link": "https://www.britannica.com/topic/test",
             "snippet": "Test article.", "pagemap": {"cse_thumbnail": [{"src": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTest123"}], "cse_image": [{"src": "https://cdn.britannica.com/123/test.jpg"}]}},
            {"position": 2, "title": "Test - Wikipedia", "link": "https://en.wikipedia.org/wiki/Test",
             "snippet": "Wikipedia article.", "pagemap": {"cse_thumbnail": [{"src": "https://encrypted-tbn1.gstatic.com/images?q=tbn:ANd9GcWiki"}]}},
        ]
    }

    def mock_get(self, url, params=None, headers=None, timeout=None, **kwargs):
        response = type('Response', (), {})()
        response.status_code = 200
        response.json = lambda: self.SERPAPI_JSON
        return response

    def test_browse_serpapi_returns_thumbnails_from_pagemap(self, monkeypatch):
        import src.search as search_mod
        monkeypatch.setattr(search_mod, 'SERP_API_KEY', 'test-key')
        monkeypatch.setattr(search_mod.requests, 'get', self.mock_get.__get__(self))
        results = search_mod.browse_serpapi_search(query='test', num_results=5, source='britannica', filters={}, user_id=9999)
        assert len(results) >= 1
        assert results[0]['thumb_url']
        assert 'gstatic.com' in results[0]['thumb_url']
        if len(results) >= 2:
            assert results[1]['thumb_url']
            assert 'gstatic.com' in results[1]['thumb_url']


# ---------------------------------------------------------------------------
# Standalone parallel multi-source search demo  (python test_search.py)
# ---------------------------------------------------------------------------

def _parallel_search_demo(label, query, num_results, sources, user_id=1):
    import time
    import concurrent.futures

    print("=" * 70)
    print(label)
    print("=" * 70)
    print(f"\nSearching for: '{query}'")
    print(f"Results per source: {num_results}")
    print(f"Sources: {', '.join(sources.keys())}\n")

    start = time.time()
    all_results = []
    source_counts = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {name: executor.submit(func, *args, user_id=user_id) for name, (func, args) in sources.items()}
        for source, future in futures.items():
            try:
                r = future.result(timeout=15)
                all_results.extend(r or [])
                source_counts[source] = len(r) if r else 0
                print(f"  {source:12} - {source_counts[source]:2} results")
            except Exception as e:
                print(f"  {source:12} - FAILED: {str(e)}")
                source_counts[source] = 0

    elapsed = time.time() - start
    print(f"\nTotal Results: {len(all_results)}")
    print(f"Total Time: {elapsed:.2f} seconds")
    print(f"Source breakdown: {source_counts}\n")

    if all_results:
        print("Sample Results (first 5):\n")
        for i, r in enumerate(all_results[:5], 1):
            print(f"{i}. [{r.get('source_name', 'unknown').upper()}] {r.get('title', 'No title')}")
            if r.get('source_url'):
                print(f"   {r['source_url'][:70]}...")
            print()


def _client_filtering_demo():
    print("=" * 70)
    print("Client-Side Result Filtering Demo")
    print("=" * 70)

    mixed = [
        {'title': 'Article 1', 'source_name': 'wikipedia'},
        {'title': 'Article 2', 'source_name': 'pubmed'},
        {'title': 'Article 3', 'source_name': 'gbooks'},
        {'title': 'Article 4', 'source_name': 'pubmed'},
        {'title': 'Article 5', 'source_name': 'wikipedia'},
        {'title': 'Article 6', 'source_name': 'gbooks'},
    ]

    print("\nMixed Results (3 sources):")
    for r in mixed:
        print(f"  - {r['title']:15} from {r['source_name']}")

    for label, sources in [
        ("Only PubMed", ['pubmed']),
        ("Academic (PubMed + Books)", ['pubmed', 'gbooks']),
        ("Only Wikipedia", ['wikipedia']),
    ]:
        filtered = [r for r in mixed if r['source_name'] in sources]
        print(f"\nFilter: {label}")
        print(f"  Result: {len(filtered)} items - {[r['title'] for r in filtered]}")
    print()


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dotenv import load_dotenv
    import src.pubmed as pubmed
    load_dotenv()

    print("\n" + "=" * 70)
    print("PARALLEL MULTI-SOURCE SEARCH TESTS")
    print("=" * 70 + "\n")

    _parallel_search_demo("Full Parallel Search", "machine learning", 10, {
        'wikipedia': (search.wikipedia, ("machine learning", 10)),
        'gbooks': (search.gbooks, ("machine learning", 10, {})),
        'pubmed': (pubmed.search, ("machine learning", 10)),
    })
    print("\n")

    _parallel_search_demo("Filtered (PubMed + Wikipedia)", "COVID-19", 5, {
        'wikipedia': (search.wikipedia, ("COVID-19", 5)),
        'pubmed': (pubmed.search, ("COVID-19", 5)),
    })
    print("\n")

    _client_filtering_demo()

    print("=" * 70)
    print("All demonstrations complete!")
    print("=" * 70 + "\n")
