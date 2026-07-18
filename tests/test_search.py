import pytest

import src.search as search
import src.whitelist as whitelist


RESPONSE_METADATA_VECTORS = (
    (
        {"source_name": "Archive", "title": "ﬀ"},
        '["display","archive","ff"]',
        "",
    ),
    (
        {"source_name": "Archive", "source_id": 1e-7},
        '["source_id","archive","1e-07"]',
        "",
    ),
    (
        {"source_url": "https://EXAMPLE.test:080/path#intro"},
        '["url","https://example.test:80/path"]',
        "https://example.test:80/path",
    ),
)


def test_result_identity_normalizes_source_but_preserves_source_id_case():
    first = {
        "source_name": "  WikiPEDIA\n Archive ",
        "source_id": "  Record-A  ",
        "source_url": "https://example.test/first",
        "title": "First",
    }
    normalized_duplicate = {
        "source_name": "wikipedia archive",
        "source_id": "Record-A",
        "source_url": "https://example.test/second",
        "title": "Second",
    }
    distinct_id = {**normalized_duplicate, "source_id": "record-a"}

    assert search.result_identity(first) == search.result_identity(normalized_duplicate)
    assert search.result_identity(first) != search.result_identity(distinct_id)


def test_canonical_source_url_normalizes_host_and_removes_fragment():
    assert search.canonical_source_url(
        " HTTPS://Example.COM/Archive/Entry?view=Full#section-two "
    ) == "https://example.com/Archive/Entry?view=Full"
    assert search.canonical_source_url("javascript://example.com/archive") == ""
    assert search.canonical_source_url("/archive/entry") == ""
    assert search.canonical_source_url("https://example.com\\archive") == ""


def test_result_identity_formats_json_scalar_source_ids_consistently():
    vectors = (
        (True, "true"),
        (False, "false"),
        (1, "1"),
        (1.0, "1"),
        (1.5, "1.5"),
    )

    for source_id, expected in vectors:
        identity = search.result_identity(
            {"source_name": "Archive", "source_id": source_id}
        )
        assert identity == ("source_id", "archive", expected)


def test_deduplicate_results_rejects_different_provider_ids_for_same_url():
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


def test_deduplicate_results_records_alias_keys_from_rejected_records():
    first = {
        "source_name": "Archive",
        "source_id": "shared-id",
        "source_url": "https://example.test/first",
        "title": "First",
    }
    repeated_id_new_url = {
        "source_name": "Archive",
        "source_id": "shared-id",
        "source_url": "https://example.test/alias",
        "title": "Repeated ID",
    }
    new_id_repeated_alias_url = {
        "source_name": "Archive",
        "source_id": "other-id",
        "source_url": "https://example.test/alias",
        "title": "Repeated alias URL",
    }

    assert search.deduplicate_results(
        [first, repeated_id_new_url, new_id_repeated_alias_url]
    ) == [first]


def test_deduplicate_results_collapses_late_alias_bridge_to_first_component_item():
    first = {
        "source_name": "Archive",
        "source_id": "shared-id",
        "source_url": "https://example.test/first",
        "title": "First",
    }
    future_alias = {
        "source_name": "Archive",
        "source_id": "other-id",
        "source_url": "https://example.test/alias",
        "title": "Future alias",
    }
    late_bridge = {
        "source_name": "Archive",
        "source_id": "shared-id",
        "source_url": "https://example.test/alias",
        "title": "Late bridge",
    }

    assert search.deduplicate_results(
        [first, future_alias, late_bridge]
    ) == [first]


def test_result_identity_falls_back_to_normalized_display_tuple():
    first = {"source_name": "  Open   Archive ", "title": "Shared\nTitle"}
    duplicate = {"source_name": "open archive", "title": " shared title "}

    assert search.result_identity(first) == search.result_identity(duplicate)
    assert search.deduplicate_results([first, duplicate]) == [first]


def test_deduplicate_results_preserves_first_seen_order_across_identity_types():
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
    repeated_identity = {
        **first,
        "source_name": " wikipedia ",
        "source_url": "https://example.test/repeated-identity",
        "title": "Repeated identity",
    }
    repeated_url = {
        "source_name": "Books",
        "source_id": "3",
        "source_url": "https://EXAMPLE.test/second#copy",
        "title": "Repeated URL",
    }
    third = {"source_name": "Archive", "title": "Third"}

    assert search.deduplicate_results(
        [first, second, repeated_identity, repeated_url, third]
    ) == [first, second, third]


def test_deduplicate_results_preserves_multiple_identity_less_records():
    malformed_one = {"description": "Missing all identity fields"}
    malformed_two = {"source_name": {"unexpected": "mapping"}, "title": ["list"]}

    assert search.result_identity(malformed_one) is None
    assert search.result_identity(malformed_two) is None
    assert search.deduplicate_results([malformed_one, malformed_two]) == [
        malformed_one,
        malformed_two,
    ]


@pytest.mark.parametrize(
    ("record", "expected_identity", "expected_url"), RESPONSE_METADATA_VECTORS
)
def test_response_dedupe_metadata_is_deterministic_copy_without_mutating_input(
    record, expected_identity, expected_url
):
    original = {**record, "provider_payload": {"rank": 1}}
    original_snapshot = {
        **original,
        "provider_payload": dict(original["provider_payload"]),
    }

    decorated = search.with_response_dedupe_metadata(original)

    assert decorated is not original
    assert decorated["_dedupe_identity"] == expected_identity
    assert decorated["_canonical_source_url"] == expected_url
    assert search.with_response_dedupe_metadata(original) == decorated
    assert original == original_snapshot
    assert "_dedupe_identity" not in original
    assert "_canonical_source_url" not in original


def test_browse_search_all_deduplicates_cards_without_changing_source_counts(monkeypatch):
    import app as flask_app

    dedicated_results = [
        {
            "source_name": "Wikipedia",
            "source_id": "wiki-1",
            "source_url": "https://EXAMPLE.test/shared#intro",
            "title": "First provider copy",
        },
        {
            "source_name": "Wikipedia",
            "source_id": "wiki-2",
            "source_url": "https://example.test/dedicated",
            "title": "Dedicated result",
        },
    ]
    whitelist_results = [
        {
            "source_name": "JSTOR",
            "source_id": "jstor-9",
            "source_url": "https://example.test/shared#abstract",
            "title": "Same URL",
        },
        {
            "source_name": " wikipedia ",
            "source_id": "wiki-2",
            "source_url": "https://example.test/repeated-id",
            "title": "Same provider identity",
        },
        {
            "source_name": "Open Archive",
            "source_id": "archive-3",
            "source_url": "https://example.test/unique",
            "title": "Unique whitelist result",
        },
    ]
    dedicated_snapshot = [dict(item) for item in dedicated_results]
    whitelist_snapshot = [dict(item) for item in whitelist_results]
    monkeypatch.setattr(
        flask_app.search,
        "wikipedia",
        lambda _query, _num_results, *, user_id: dedicated_results,
    )
    monkeypatch.setattr(
        flask_app.search,
        "whitelist_search",
        lambda _query, _num_results, *, user_id: whitelist_results,
    )

    with flask_app.app.test_request_context(
        "/api/browse/search-all",
        method="POST",
        json={
            "query": "archive",
            "sources": ["wikipedia", "whitelist"],
            "num_results": 10,
        },
    ):
        flask_app.session["user_id"] = 7
        response = flask_app.browse_search_all()

    payload = response.get_json()
    assert [item["title"] for item in payload["results"]] == [
        "First provider copy",
        "Dedicated result",
        "Unique whitelist result",
    ]
    assert [item["_dedupe_identity"] for item in payload["results"]] == [
        '["source_id","wikipedia","wiki-1"]',
        '["source_id","wikipedia","wiki-2"]',
        '["source_id","open archive","archive-3"]',
    ]
    assert [item["_canonical_source_url"] for item in payload["results"]] == [
        "https://example.test/shared",
        "https://example.test/dedicated",
        "https://example.test/unique",
    ]
    assert payload["source_counts"] == {"wikipedia": 2, "whitelist": 3}
    assert {
        source: [item["title"] for item in items]
        for source, items in payload["grouped_results"].items()
    } == {
        "wikipedia": ["First provider copy", "Dedicated result"],
        "whitelist": ["Unique whitelist result"],
    }
    assert dedicated_results == dedicated_snapshot
    assert whitelist_results == whitelist_snapshot
    assert all("_dedupe_identity" not in item for item in dedicated_results)
    assert all("_dedupe_identity" not in item for item in whitelist_results)


def test_browse_search_all_cleans_duplicate_and_overlapping_source_selections(
    monkeypatch,
):
    import app as flask_app

    calls = []

    def fake_wikipedia(_query, _num_results, *, user_id):
        calls.append(("wikipedia", user_id))
        return [{
            "source_name": "Wikipedia",
            "source_id": "wiki-1",
            "source_url": "https://en.wikipedia.org/wiki/Archive",
            "title": "Wikipedia",
        }]

    def fake_gbooks(_query, _num_results, _filters, *, user_id):
        calls.append(("gbooks", user_id))
        return [{
            "source_name": "gbooks",
            "source_id": "book-1",
            "source_url": "https://books.google.com/books?id=book-1",
            "title": "Book",
        }]

    def fake_whitelist(_query, _num_results, domains=None, *, user_id):
        calls.append(("whitelist", tuple(domains or ()), user_id))
        return [{
            "source_name": "Wikipedia",
            "source_id": "wiki-1",
            "source_url": "https://en.wikipedia.org/wiki/Archive",
            "title": "Duplicate Wikipedia",
        }]

    monkeypatch.setattr(flask_app.search, "wikipedia", fake_wikipedia)
    monkeypatch.setattr(flask_app.search, "gbooks", fake_gbooks)
    monkeypatch.setattr(flask_app.search, "whitelist_search", fake_whitelist)

    with flask_app.app.test_request_context(
        "/api/browse/search-all",
        method="POST",
        json={
            "query": "archive",
            "sources": [
                "wikipedia",
                "wikipedia",
                "whitelist",
                "whitelist_en.wikipedia.org",
                "gbooks",
            ],
            "num_results": 10,
        },
    ):
        flask_app.session["user_id"] = 9
        response = flask_app.browse_search_all()

    payload = response.get_json()
    assert len(calls) == 3
    assert calls.count(("wikipedia", 9)) == 1
    assert calls.count(("whitelist", ("en.wikipedia.org",), 9)) == 1
    assert calls.count(("gbooks", 9)) == 1
    assert set(payload["grouped_results"]) == {
        "wikipedia",
        "whitelist_en.wikipedia.org",
        "gbooks",
    }
    assert [item["title"] for item in payload["results"]] == ["Wikipedia", "Book"]


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

    def fake_get(url, params=None, headers=None, timeout=None):
        assert url == "https://serpapi.com/search"
        assert params["api_key"] == "test-key"
        assert params["engine"] == "google"
        assert "site:en.wikipedia.org" in params["q"]
        class FakeResponse:
            status_code = 200
            def json(self_non):
                return {
                    "organic_results": [
                        {
                            "link": "https://en.wikipedia.org/wiki/Test",
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

    results = search.whitelist_search("test query", 1, user_id=1)

    assert len(results) == 1
    assert results[0]["source_url"] == "https://en.wikipedia.org/wiki/Test"


@pytest.mark.parametrize(
    ("requested", "expected"),
    ((-5, 0), (0, 0), (40, 40), (41, 40), (500, 40)),
)
def test_gbooks_clamps_max_results_to_api_bounds(monkeypatch, requested, expected):
    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"items": []}

    def fake_get(url, *, params, headers, timeout):
        captured.update(
            url=url,
            params=dict(params),
            headers=dict(headers),
            timeout=timeout,
        )
        return FakeResponse()

    monkeypatch.setattr(search.requests, "get", fake_get)

    assert search.gbooks("archive", requested, {}, user_id=7) == []
    assert captured["url"] == "https://www.googleapis.com/books/v1/volumes"
    assert captured["params"] == {"q": "archive", "maxResults": expected}
    assert captured["headers"] == {"User-Agent": search.USER_AGENT}
    assert captured["timeout"] == 10


def test_gbooks_merges_filtered_access_info_after_persistence(monkeypatch):
    existing_record = {
        "id": 21,
        "title": "Stored title",
        "description": "Stored description",
        "thumb_url": "https://books.google.com/cover-existing.jpg",
        "source_url": "https://books.google.com/books?id=existing-volume",
        "source_name": "gbooks",
        "source_id": "existing-volume",
    }
    created_payloads = []
    captured_params = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "items": [
                    {
                        "id": "existing-volume",
                        "volumeInfo": {
                            "title": "Fresh existing title",
                            "description": "Fresh existing description",
                            "infoLink": "https://books.google.com/books?id=existing-volume",
                        },
                        "accessInfo": {
                            "embeddable": True,
                            "webReaderLink": "https://books.google.com/books/reader?id=existing-volume",
                            "viewability": "PARTIAL",
                            "accessViewStatus": "SAMPLE",
                            "country": "AU",
                            "downloadAccess": {"deviceAllowed": True},
                        },
                    },
                    {
                        "id": "new-volume",
                        "volumeInfo": {
                            "title": "New title",
                            "description": "New description",
                            "infoLink": "https://books.google.com/books?id=new-volume",
                        },
                        "accessInfo": {"embeddable": 1},
                    },
                ]
            }

    def fake_get(_url, *, params, headers, timeout):
        captured_params.update(params)
        assert headers == {"User-Agent": search.USER_AGENT}
        assert timeout == 10
        return FakeResponse()

    def fake_get_item(source_name, source_id, user_id, add_to_recent_search):
        assert (source_name, user_id, add_to_recent_search) == ("gbooks", 9, True)
        return existing_record if source_id == "existing-volume" else None

    def fake_create_item(item_data, user_id, add_to_recent_search):
        assert (user_id, add_to_recent_search) == (9, True)
        created_payloads.append(dict(item_data))
        return {"id": 22, **item_data}

    monkeypatch.setattr(search.requests, "get", fake_get)
    monkeypatch.setattr(search.whitelist, "is_allowed", lambda _url: True)
    monkeypatch.setattr(search.db, "get_item_by_source", fake_get_item)
    monkeypatch.setattr(search.db, "create_item", fake_create_item)

    results = search.gbooks(
        "viewer",
        100,
        {"download": "epub", "available": "partial", "print": "books"},
        user_id=9,
    )

    assert captured_params == {
        "q": "viewer",
        "maxResults": 40,
        "download": "epub",
        "filter": "partial",
        "printType": "books",
    }
    assert [result["source_id"] for result in results] == [
        "existing-volume",
        "new-volume",
    ]
    assert results[0]["accessInfo"] == {
        "embeddable": True,
        "webReaderLink": "https://books.google.com/books/reader?id=existing-volume",
        "viewability": "PARTIAL",
        "accessViewStatus": "SAMPLE",
    }
    assert results[1]["accessInfo"] == {
        "embeddable": False,
        "webReaderLink": "",
        "viewability": "UNKNOWN",
        "accessViewStatus": "NONE",
    }
    assert results[0] is not existing_record
    assert "accessInfo" not in existing_record
    assert len(created_payloads) == 1
    assert created_payloads[0]["source_id"] == "new-volume"
    assert "accessInfo" not in created_payloads[0]

    decorated = search.with_response_dedupe_metadata(results[0])
    assert decorated["accessInfo"] == results[0]["accessInfo"]
    assert decorated["_dedupe_identity"] == '["source_id","gbooks","existing-volume"]'
    assert decorated["_canonical_source_url"] == (
        "https://books.google.com/books?id=existing-volume"
    )


def _install_search_result_persistence(monkeypatch):
    monkeypatch.setattr(search.whitelist, "is_allowed", lambda _url: True)
    monkeypatch.setattr(
        search.whitelist,
        "get_domain",
        lambda url: url.split("/", 3)[2],
    )
    monkeypatch.setattr(
        search.whitelist,
        "get_display_name_for_domain",
        lambda domain: domain,
    )
    monkeypatch.setattr(search.db, "get_item_by_source", lambda *_args: None)
    monkeypatch.setattr(
        search.db,
        "create_item",
        lambda item_data, _user_id, _add_to_recent_search: item_data,
    )


def _custom_search_items(domain, start, count):
    return [
        {
            "link": f"https://{domain}/result-{index}",
            "title": f"Result {index}",
            "snippet": f"Snippet {index}",
        }
        for index in range(start, start + count)
    ]


def test_google_scholar_paginates_custom_search_to_requested_count(monkeypatch):
    requests_seen = []

    class FakeResponse:
        status_code = 200

        def __init__(self, items):
            self._items = items

        def json(self):
            return {"items": self._items}

    def fake_get(url, *, params, headers, timeout):
        requests_seen.append((url, dict(params), dict(headers), timeout))
        return FakeResponse(
            _custom_search_items("scholar.google.com", params["start"], params["num"])
        )

    monkeypatch.setattr(search, "GOOGLE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(search, "GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    monkeypatch.setattr(search.requests, "get", fake_get)
    _install_search_result_persistence(monkeypatch)

    results = search.google_scholar("archive", 25, user_id=4)

    assert len(results) == 25
    assert [request[1]["start"] for request in requests_seen] == [1, 11, 21]
    assert [request[1]["num"] for request in requests_seen] == [10, 10, 5]
    assert all(request[0] == "https://www.googleapis.com/customsearch/v1" for request in requests_seen)
    assert all(request[2] == {"User-Agent": search.USER_AGENT} for request in requests_seen)
    assert all(request[3] == 10 for request in requests_seen)


def test_google_scholar_stops_after_short_custom_search_page(monkeypatch):
    starts = []

    class FakeResponse:
        status_code = 200

        def __init__(self, items):
            self._items = items

        def json(self):
            return {"items": self._items}

    def fake_get(_url, *, params, headers, timeout):
        assert headers == {"User-Agent": search.USER_AGENT}
        assert timeout == 10
        starts.append(params["start"])
        count = 10 if params["start"] == 1 else 3
        return FakeResponse(
            _custom_search_items("scholar.google.com", params["start"], count)
        )

    monkeypatch.setattr(search, "GOOGLE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(search, "GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    monkeypatch.setattr(search.requests, "get", fake_get)
    _install_search_result_persistence(monkeypatch)

    results = search.google_scholar("archive", 30, user_id=4)

    assert len(results) == 13
    assert starts == [1, 11]


def test_google_scholar_discards_entire_malformed_later_page(monkeypatch):
    starts = []

    class FakeResponse:
        status_code = 200

        def __init__(self, items):
            self._items = items

        def json(self):
            return {"items": self._items}

    def fake_get(_url, *, params, headers, timeout):
        assert headers == {"User-Agent": search.USER_AGENT}
        assert timeout == 10
        starts.append(params["start"])
        if params["start"] == 1:
            items = _custom_search_items("scholar.google.com", 1, 10)
        else:
            items = _custom_search_items("scholar.google.com", 11, 9) + [None]
        return FakeResponse(items)

    monkeypatch.setattr(search, "GOOGLE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(search, "GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    monkeypatch.setattr(search.requests, "get", fake_get)
    _install_search_result_persistence(monkeypatch)

    results = search.google_scholar("archive", 20, user_id=4)

    assert len(results) == 10
    assert [item["source_id"] for item in results] == [
        f"https://scholar.google.com/result-{index}" for index in range(1, 11)
    ]
    assert starts == [1, 11]


def test_explicit_whitelist_custom_search_paginates_instead_of_repeating_first_page(
    monkeypatch,
):
    requests_seen = []

    class FakeResponse:
        status_code = 200

        def __init__(self, items):
            self._items = items

        def json(self):
            return {"items": self._items}

    def fake_get(_url, *, params, headers, timeout):
        requests_seen.append(dict(params))
        assert headers == {"User-Agent": search.USER_AGENT}
        assert timeout == 10
        return FakeResponse(
            _custom_search_items("en.wikipedia.org", params["start"], params["num"])
        )

    monkeypatch.setattr(search, "SERP_API_KEY", "")
    monkeypatch.setattr(search, "GOOGLE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(search, "GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    monkeypatch.setattr(search.requests, "get", fake_get)
    _install_search_result_persistence(monkeypatch)

    results = search.whitelist_search(
        "archive",
        23,
        domains=["en.wikipedia.org"],
        user_id=8,
    )

    assert len(results) == 23
    assert [params["start"] for params in requests_seen] == [1, 11, 21]
    assert [params["num"] for params in requests_seen] == [10, 10, 3]
    assert all("site:en.wikipedia.org" in params["q"] for params in requests_seen)


def test_explicit_whitelist_discards_entire_malformed_later_page(monkeypatch):
    starts = []

    class FakeResponse:
        status_code = 200

        def __init__(self, items):
            self._items = items

        def json(self):
            return {"items": self._items}

    def fake_get(_url, *, params, headers, timeout):
        assert headers == {"User-Agent": search.USER_AGENT}
        assert timeout == 10
        starts.append(params["start"])
        if params["start"] == 1:
            items = _custom_search_items("en.wikipedia.org", 1, 10)
        else:
            items = _custom_search_items("en.wikipedia.org", 11, 9) + [False]
        return FakeResponse(items)

    monkeypatch.setattr(search, "SERP_API_KEY", "")
    monkeypatch.setattr(search, "GOOGLE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(search, "GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    monkeypatch.setattr(search.requests, "get", fake_get)
    _install_search_result_persistence(monkeypatch)

    results = search.whitelist_search(
        "archive",
        20,
        domains=["en.wikipedia.org"],
        user_id=8,
    )

    assert len(results) == 10
    assert [item["source_id"] for item in results] == [
        f"https://en.wikipedia.org/result-{index}" for index in range(1, 11)
    ]
    assert starts == [1, 11]


def test_serpapi_whitelist_search_paginates_and_stops_on_empty_page(monkeypatch):
    starts = []

    class FakeResponse:
        status_code = 200

        def __init__(self, items):
            self._items = items

        def json(self):
            return {"organic_results": self._items}

    def fake_get(_url, *, params, headers, timeout):
        assert headers == {"User-Agent": search.USER_AGENT}
        assert timeout == 10
        starts.append(params["start"])
        count = 10 if params["start"] == 0 else 0
        return FakeResponse(
            _custom_search_items("en.wikipedia.org", params["start"], count)
        )

    monkeypatch.setattr(search, "SERP_API_KEY", "test-key")
    monkeypatch.setattr(search.requests, "get", fake_get)
    _install_search_result_persistence(monkeypatch)

    results = search.whitelist_search(
        "archive",
        20,
        domains=["en.wikipedia.org"],
        user_id=8,
    )

    assert len(results) == 10
    assert starts == [0, 10]


def test_serpapi_malformed_later_page_preserves_accumulated_results(monkeypatch):
    starts = []

    class FakeResponse:
        status_code = 200

        def __init__(self, start):
            self._start = start

        def json(self):
            if self._start == 10:
                raise ValueError("malformed JSON")
            return {
                "organic_results": _custom_search_items(
                    "en.wikipedia.org", self._start, 10
                )
            }

    def fake_get(_url, *, params, headers, timeout):
        assert headers == {"User-Agent": search.USER_AGENT}
        assert timeout == 10
        starts.append(params["start"])
        return FakeResponse(params["start"])

    monkeypatch.setattr(search, "SERP_API_KEY", "test-key")
    monkeypatch.setattr(search.requests, "get", fake_get)
    _install_search_result_persistence(monkeypatch)

    results = search.whitelist_search(
        "archive",
        20,
        domains=["en.wikipedia.org"],
        user_id=8,
    )

    assert len(results) == 10
    assert starts == [0, 10]


def test_serpapi_malformed_later_result_list_preserves_accumulated_results(
    monkeypatch,
):
    starts = []

    class FakeResponse:
        status_code = 200

        def __init__(self, start):
            self._start = start

        def json(self):
            if self._start == 10:
                return {"organic_results": [None]}
            return {
                "organic_results": _custom_search_items(
                    "en.wikipedia.org", self._start, 10
                )
            }

    def fake_get(_url, *, params, headers, timeout):
        assert headers == {"User-Agent": search.USER_AGENT}
        assert timeout == 10
        starts.append(params["start"])
        return FakeResponse(params["start"])

    monkeypatch.setattr(search, "SERP_API_KEY", "test-key")
    monkeypatch.setattr(search.requests, "get", fake_get)
    _install_search_result_persistence(monkeypatch)

    results = search.whitelist_search(
        "archive",
        20,
        domains=["en.wikipedia.org"],
        user_id=8,
    )

    assert len(results) == 10
    assert starts == [0, 10]


def test_google_custom_search_stays_within_final_100_result_boundary(monkeypatch):
    requests_seen = []

    class FakeResponse:
        status_code = 200

        def __init__(self, items):
            self._items = items

        def json(self):
            return {"items": self._items}

    def fake_get(_url, *, params, headers, timeout):
        requests_seen.append(dict(params))
        assert headers == {"User-Agent": search.USER_AGENT}
        assert timeout == 10
        return FakeResponse(
            _custom_search_items("scholar.google.com", params["start"], params["num"])
        )

    monkeypatch.setattr(search, "GOOGLE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(search, "GOOGLE_SEARCH_ENGINE_ID", "test-cx")
    monkeypatch.setattr(search.requests, "get", fake_get)

    results = search._google_custom_search_items("archive", 101)

    assert len(results) == 99
    assert requests_seen[-1]["start"] == 91
    assert requests_seen[-1]["num"] == 9
    assert all(params["start"] + params["num"] <= 100 for params in requests_seen)
