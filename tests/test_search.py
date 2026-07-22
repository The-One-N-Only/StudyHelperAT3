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
    monkeypatch.setattr(flask_app.search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(
        flask_app.search,
        "browse_serpapi_search",
        lambda _query, _num_results, source, _filters, *, user_id: (
            dedicated_results if source == "wikipedia" else whitelist_results
        ),
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

    def fake_browse(_query, _num_results, source, _filters, *, user_id):
        calls.append((source, user_id))
        if source == "wikipedia":
            return [{
                "source_name": "Wikipedia",
                "source_id": "wiki-1",
                "source_url": "https://en.wikipedia.org/wiki/Archive",
                "title": "Wikipedia",
            }]
        if source == "gbooks":
            return [{
                "source_name": "gbooks",
                "source_id": "book-1",
                "source_url": "https://books.google.com/books?id=book-1",
                "title": "Book",
            }]
        return [{
            "source_name": "Wikipedia",
            "source_id": "wiki-1",
            "source_url": "https://en.wikipedia.org/wiki/Archive",
            "title": "Duplicate Wikipedia",
        }]

    monkeypatch.setattr(flask_app.search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(flask_app.search, "browse_serpapi_search", fake_browse)

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
    assert len(calls) == 2
    assert calls.count(("wikipedia", 9)) == 1
    assert calls.count(("whitelist_en.wikipedia.org", 9)) == 0
    assert calls.count(("gbooks", 9)) == 1
    assert set(payload["grouped_results"]) == {
        "wikipedia",
        "gbooks",
    }
    assert [item["title"] for item in payload["results"]] == ["Wikipedia", "Book"]


def test_whitelist_search_uses_one_combined_serpapi_scope(monkeypatch):
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
        (
            "test query",
            10,
            "site:en.wikipedia.org OR site:pubmed.ncbi.nlm.nih.gov",
            1,
        )
    ]


def test_whitelist_search_respects_domains_argument(monkeypatch):
    scopes = []

    def fake_serp(_query, _num_results, scope, *, user_id):
        assert user_id == 2
        scopes.append(scope)
        return []

    monkeypatch.setattr(search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(search, "_search_serpapi", fake_serp)
    monkeypatch.setattr(
        whitelist,
        "get_whitelisted_domains",
        lambda: ["books.google.com"],
    )

    search.whitelist_search(
        "example",
        1,
        domains=["books.google.com", "not-approved.test"],
        user_id=2,
    )

    assert scopes == ["site:books.google.com"]


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
    monkeypatch.setattr(search.whitelist, "get_whitelist_search_scope", lambda: "site:en.wikipedia.org")
    monkeypatch.setattr(search.db, "get_search_cache", lambda key: None)
    monkeypatch.setattr(search.db, "get_or_create_item", lambda item_data, user_id, add_to_recent_search: {"id": 0, **item_data})

    results = search.whitelist_search("test query", 1, user_id=1)

    assert len(results) == 1
    assert results[0]["source_url"] == "https://en.wikipedia.org/wiki/Test"


def _run_browse_serpapi_image_results(
    monkeypatch,
    organic_results,
    *,
    source="wikipedia",
    allowed_image_prefixes=(),
):
    requests_seen = []

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"organic_results": organic_results}

    def fake_get(url, *, params, headers, timeout):
        requests_seen.append((url, dict(params), dict(headers), timeout))
        return FakeResponse()

    def is_allowed(url):
        return (
            url.startswith("https://en.wikipedia.org/wiki/")
            or url.startswith("https://books.google.com/books")
            or any(url.startswith(prefix) for prefix in allowed_image_prefixes)
        )

    monkeypatch.setattr(search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(search.requests, "get", fake_get)
    monkeypatch.setattr(search.whitelist, "is_allowed", is_allowed)
    monkeypatch.setattr(search.db, "get_search_cache", lambda key: None)
    monkeypatch.setattr(
        search.db,
        "get_or_create_item",
        lambda item_data, _user_id, _recent: {"id": 0, **item_data},
    )
    results = search.browse_serpapi_search(
        "archive",
        len(organic_results),
        source,
        {},
        user_id=7,
    )
    return results, requests_seen


def test_browse_serpapi_gbooks_cover_from_query_id_precedes_hostile_metadata(
    monkeypatch,
):
    link = "https://books.google.com/books?id=zyTCAlFPjgYC&hl=en"
    results, requests_seen = _run_browse_serpapi_image_results(
        monkeypatch,
        [{
            "title": "Book",
            "link": link,
            "thumbnail": "https://attacker@serpapi.com/hostile.jpg",
            "favicon": "https://serpapi.com/safe-but-lower-priority.png",
        }],
        source="gbooks",
    )

    assert results[0]["thumb_url"] == (
        "https://books.google.com/books/content?id=zyTCAlFPjgYC"
        "&printsec=frontcover&img=1&zoom=1"
    )
    assert results[0]["thumb_mime"] == "image/jpeg"
    assert results[0]["thumb_height"] == 0
    assert results[0]["source_id"] == link
    assert results[0]["google_books_volume_id"] == "zyTCAlFPjgYC"
    assert len(requests_seen) == 1


def test_browse_serpapi_gbooks_cover_supports_edition_path_id(monkeypatch):
    results, _requests_seen = _run_browse_serpapi_image_results(
        monkeypatch,
        [{
            "title": "Edition",
            "link": (
                "https://books.google.com/books/edition/Archive_Studies/"
                "_o3BjwEACAAJ?hl=en"
            ),
            "thumbnail": "https://tracking.invalid/hostile.jpg",
        }],
        source="gbooks",
    )

    assert results[0]["thumb_url"] == (
        "https://books.google.com/books/content?id=_o3BjwEACAAJ"
        "&printsec=frontcover&img=1&zoom=1"
    )


@pytest.mark.parametrize(
    "source_url",
    (
        "https://user:password@books.google.com/books?id=zyTCAlFPjgYC",
        "https://books.google.com:444/books?id=zyTCAlFPjgYC",
        "https://books.google.com/books?id=zyTCAlFPjgYC#fragment",
        "https://books.google.com/books\\?id=zyTCAlFPjgYC",
        "https://books.google.com/books?id=zyTCAlF PjgYC",
        "https://[broken/books?id=zyTCAlFPjgYC",
    ),
)
def test_browse_serpapi_gbooks_cover_rejects_unsafe_source_url(source_url):
    assert search._google_books_volume_id(source_url) == ""
    assert search._google_books_cover_url(source_url) == ""


def test_browse_serpapi_gbooks_cover_applies_to_explicit_whitelist_source(
    monkeypatch,
):
    link = "https://books.google.com/books?id=whitelist-book-1"
    results, requests_seen = _run_browse_serpapi_image_results(
        monkeypatch,
        [{
            "title": "Whitelisted book",
            "link": link,
            "thumbnail": "https://tracking.invalid/hostile.jpg",
        }],
        source="whitelist_books.google.com",
    )

    assert results[0]["thumb_url"] == (
        "https://books.google.com/books/content?id=whitelist-book-1"
        "&printsec=frontcover&img=1&zoom=1"
    )
    assert results[0]["source_name"] == "Google Books"
    assert results[0]["source_id"] == link
    assert len(requests_seen) == 1
    assert requests_seen[0][1]["q"] == "archive site:books.google.com"


@pytest.mark.parametrize(
    "item",
    (
        {"source_id": "VpNa9UckT24C"},
        {
            "link": "https://books.google.com/books?hl=en",
            "source_id": "VpNa9UckT24C",
        },
        {
            "link": "https://user:password@books.google.com/books?id=hostile",
            "source_id": "VpNa9UckT24C",
        },
    ),
)
def test_browse_serpapi_gbooks_cover_accepts_bounded_raw_source_id_independently(
    item,
):
    assert search._browse_result_image_url(item) == (
        "https://books.google.com/books/content?id=VpNa9UckT24C"
        "&printsec=frontcover&img=1&zoom=1"
    )


def test_browse_serpapi_preserves_raw_books_id_after_source_id_normalization(
    monkeypatch,
):
    link = "https://books.google.com/books?hl=en"
    results, _requests_seen = _run_browse_serpapi_image_results(
        monkeypatch,
        [{
            "title": "Previewable book",
            "link": link,
            "source_id": "VpNa9UckT24C",
        }],
        source="gbooks",
    )

    assert results[0]["source_id"] == link
    assert results[0]["google_books_volume_id"] == "VpNa9UckT24C"


@pytest.mark.parametrize(
    "item",
    (
        {
            "link": "https://evil.example/books?hl=en",
            "source_id": "VpNa9UckT24C",
        },
        {
            "link": "https://books.google.com/books?hl=en",
            "source_id": "VpNa9UckT24C/extra",
        },
        {
            "link": "https://user@books.google.com/books?hl=en",
            "source_id": "VpNa9UckT24C",
        },
        {
            "link": "https://books.google.com/books?hl=en",
            "source_id": "https://evil.example/books?id=VpNa9UckT24C",
        },
    ),
)
def test_google_books_volume_id_rejects_untrusted_ids_and_hosts(item):
    assert search._google_books_volume_id(item) == ""


@pytest.mark.parametrize(
    "source_id",
    (
        "VpNa9UckT24C/extra",
        "VpNa9UckT24C?download=1",
        " VpNa9UckT24C",
        "A" * 221,
        "https://evil.example/books?id=VpNa9UckT24C",
        "https://user:password@books.google.com/books?id=VpNa9UckT24C",
        "https://books.google.com:444/books?id=VpNa9UckT24C",
        "https://books.google.com/books?id=VpNa9UckT24C#fragment",
    ),
)
def test_browse_serpapi_gbooks_cover_rejects_invalid_raw_or_url_source_id(
    source_id,
):
    safe_thumbnail = "https://serpapi.com/safe.jpg"

    assert search._browse_result_image_url({
        "link": "https://books.google.com/books?hl=en",
        "source_id": source_id,
        "thumbnail": safe_thumbnail,
    }) == safe_thumbnail


def test_browse_serpapi_gbooks_cover_does_not_treat_raw_result_link_as_volume_id():
    assert search._browse_result_image_url({"link": "VpNa9UckT24C"}) == ""


@pytest.mark.parametrize(
    ("thumbnail", "favicon", "allowed_prefixes", "expected"),
    (
        (
            "https://serpapi.com/images/thumb.jpeg",
            "https://gstatic.com/favicon.png",
            (),
            "https://serpapi.com/images/thumb.jpeg",
        ),
        (
            "https://tracking.invalid/thumb.jpg",
            "https://www.gstatic.com/favicon.png",
            (),
            "https://www.gstatic.com/favicon.png",
        ),
        (
            "https://lh3.googleusercontent.com/cover.jpg",
            "",
            (),
            "https://lh3.googleusercontent.com/cover.jpg",
        ),
        (
            "https://books.google.com/cover.jpg",
            "",
            (),
            "https://books.google.com/cover.jpg",
        ),
        (
            "https://upload.wikimedia.org/cover.jpg",
            "",
            (),
            "https://upload.wikimedia.org/cover.jpg",
        ),
        (
            "https://images.example.edu/cover.jpg",
            "",
            ("https://images.example.edu/",),
            "https://images.example.edu/cover.jpg",
        ),
    ),
)
def test_browse_serpapi_thumbnail_then_favicon_accepts_only_approved_https_hosts(
    monkeypatch,
    thumbnail,
    favicon,
    allowed_prefixes,
    expected,
):
    results, _requests_seen = _run_browse_serpapi_image_results(
        monkeypatch,
        [{
            "title": "Archive",
            "link": "https://en.wikipedia.org/wiki/Archive",
            "thumbnail": thumbnail,
            "favicon": favicon,
        }],
        allowed_image_prefixes=allowed_prefixes,
    )

    assert results[0]["thumb_url"] == expected
    assert results[0]["thumb_mime"] == "image/jpeg"
    assert results[0]["thumb_height"] == 0


@pytest.mark.parametrize(
    "image_url",
    (
        "http://serpapi.com/image.jpg",
        "https://user:password@serpapi.com/image.jpg",
        "https://serpapi.com:444/image.jpg",
        "https://serpapi.com/image.jpg#fragment",
        "https://serpapi.com/image name.jpg",
        "https://serpapi.com\\image.jpg",
        "https://evilserpapi.com/image.jpg",
        "https://tracking.invalid/image.jpg",
        "https://[broken/image.jpg",
        "https://serpapi.com/" + ("a" * 240),
    ),
)
def test_browse_serpapi_image_rejects_unsafe_or_oversized_metadata(
    monkeypatch,
    image_url,
):
    results, requests_seen = _run_browse_serpapi_image_results(
        monkeypatch,
        [{
            "title": "Archive",
            "link": "https://en.wikipedia.org/wiki/Archive",
            "thumbnail": image_url,
            "favicon": image_url,
        }],
    )

    assert results[0]["thumb_url"] == ""
    assert results[0]["thumb_height"] == 0
    assert len(requests_seen) == 1


def test_browse_serpapi_cover_falls_back_empty_when_generated_url_exceeds_db_limit(
    monkeypatch,
):
    long_id = "A" * 220
    results, _requests_seen = _run_browse_serpapi_image_results(
        monkeypatch,
        [{
            "title": "Oversized edition",
            "link": f"https://books.google.com/books?id={long_id}",
            "thumbnail": "https://serpapi.com/" + ("a" * 240),
        }],
        source="gbooks",
    )

    assert results[0]["thumb_url"] == ""


@pytest.mark.parametrize(
    ("source", "domain", "source_name"),
    (
        ("wikipedia", "en.wikipedia.org", "wikipedia"),
        ("gbooks", "books.google.com", "gbooks"),
        ("scholar", "scholar.google.com", "scholar"),
        ("pubmed", "pubmed.ncbi.nlm.nih.gov", "pubmed"),
    ),
)
def test_browse_serpapi_search_scopes_every_dedicated_source(
    monkeypatch, source, domain, source_name
):
    requests_seen = []

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "search_metadata": {"status": "Success"},
                "search_parameters": {"engine": "google"},
                "organic_results": [
                    {
                        "position": 1,
                        "title": "Scoped result",
                        "link": f"https://{domain}/result",
                        "displayed_link": f"https://{domain} / result",
                        "snippet": "Scoped snippet",
                        "thumbnail": "https://tracking.invalid/pixel.jpg",
                    }
                ],
                "serpapi_pagination": {},
            }

    def fake_get(url, *, params, headers, timeout):
        requests_seen.append((url, dict(params), dict(headers), timeout))
        return FakeResponse()

    monkeypatch.setattr(search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(search.requests, "get", fake_get)
    monkeypatch.setattr(
        search.whitelist,
        "is_allowed",
        lambda url: url.startswith(f"https://{domain}/"),
    )
    monkeypatch.setattr(search.db, "get_search_cache", lambda key: None)
    monkeypatch.setattr(
        search.db,
        "get_or_create_item",
        lambda item_data, _user_id, _add_to_recent_search: {"id": 0, **item_data},
    )

    results = search.browse_serpapi_search(
        "archive research",
        1,
        source,
        {
            "min_date": "2020",
            "max_date": "2024",
            "content_type": "review",
        },
        user_id=7,
    )

    assert len(results) == 1
    assert results[0]["source_name"] == source_name
    assert results[0]["source_url"] == f"https://{domain}/result"
    assert results[0]["thumb_url"] == ""
    assert requests_seen == [
        (
            "https://serpapi.com/search",
            {
                "q": (
                    f'archive research site:{domain} after:2019-12-31 '
                    'before:2025-01-01 "review"'
                ),
                "num": 1,
                "start": 0,
                "api_key": "serp-test-key",
                "engine": "google",
            },
            {"User-Agent": search.USER_AGENT},
            10,
        )
    ]


def test_browse_serpapi_search_supports_checked_wildcard_domain_pattern(monkeypatch):
    requests_seen = []

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "organic_results": [{
                    "title": "University result",
                    "link": "https://example.edu/research",
                    "snippet": "Academic result",
                }]
            }

    def fake_get(_url, *, params, headers, timeout):
        requests_seen.append(dict(params))
        return FakeResponse()

    monkeypatch.setattr(search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(search.requests, "get", fake_get)
    monkeypatch.setattr(search.whitelist, "get_whitelisted_domains", lambda: [])
    monkeypatch.setattr(
        search.whitelist,
        "get_whitelisted_domain_patterns",
        lambda: ["*.edu"],
        raising=False,
    )
    monkeypatch.setattr(search.whitelist, "is_allowed", lambda _url: True)
    monkeypatch.setattr(search.db, "get_search_cache", lambda key: None)
    monkeypatch.setattr(
        search.db,
        "get_or_create_item",
        lambda item_data, _user_id, _recent: {"id": 0, **item_data},
        raising=False,
    )

    results = search.browse_serpapi_search(
        "archive",
        1,
        "whitelist_*.edu",
        {},
        user_id=7,
    )

    assert requests_seen[0]["q"] == "archive site:*.edu"
    assert results[0]["source_url"] == "https://example.edu/research"
    assert results[0]["source_name"] == "All edu sites"


def test_combined_whitelist_scope_is_parenthesized_before_filters():
    assert search._browse_serp_query(
        "archive",
        "site:example.edu OR site:example.gov",
        {"min_date": "2020"},
    ) == "archive (site:example.edu OR site:example.gov) after:2019-12-31"


def test_browse_serpapi_search_requires_key_before_network_or_database(monkeypatch):
    monkeypatch.setattr(search, "SERP_API_KEY", "")

    def unexpected(*_args, **_kwargs):
        raise AssertionError("provider and database work must not start")

    monkeypatch.setattr(search.requests, "get", unexpected)
    monkeypatch.setattr(search.db, "get_or_create_item", unexpected)

    with pytest.raises(search.SerpApiConfigurationError):
        search.browse_serpapi_search(
            "archive",
            10,
            "wikipedia",
            {},
            user_id=7,
        )


def test_browse_search_all_dispatches_every_source_through_serpapi(monkeypatch):
    import app as flask_app

    calls = []

    def fake_serp(query, num_results, source, filters, *, user_id):
        calls.append((query, num_results, source, filters, user_id))
        return [
            {
                "source_name": source,
                "source_id": f"https://example.test/{source}",
                "source_url": f"https://example.test/{source}",
                "title": source,
            }
        ]

    def unexpected(*_args, **_kwargs):
        raise AssertionError("Browse called an individual provider API")

    monkeypatch.setattr(flask_app.search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(
        flask_app.search,
        "browse_serpapi_search",
        fake_serp,
        raising=False,
    )
    monkeypatch.setattr(flask_app.search, "wikipedia", unexpected)
    monkeypatch.setattr(flask_app.search, "gbooks", unexpected)
    monkeypatch.setattr(flask_app.search, "whitelist_search", unexpected)
    monkeypatch.setattr(flask_app.pubmed, "search", unexpected)

    with flask_app.app.test_request_context(
        "/api/browse/search-all",
        method="POST",
        json={
            "query": "archive",
            "sources": [
                "wikipedia",
                "gbooks",
                "scholar",
                "pubmed",
                "whitelist_en.wikipedia.org",
            ],
            "num_results": 10,
            "filters": {"content_type": "review"},
        },
    ):
        flask_app.session["user_id"] = 9
        response = flask_app.browse_search_all()

    payload = response.get_json()
    assert payload["status"] is True
    assert sorted(call[2] for call in calls) == [
        "gbooks",
        "pubmed",
        "scholar",
        "wikipedia",
    ]
    assert all(call[0] == "archive" for call in calls)
    assert all(call[1] == 10 for call in calls)
    assert all(call[3] == {"content_type": "review"} for call in calls)
    assert all(call[4] == 9 for call in calls)


def test_browse_routes_return_clear_missing_serpapi_configuration(monkeypatch):
    import app as flask_app

    monkeypatch.setattr(flask_app.search, "SERP_API_KEY", "")
    expected_error = (
        "Browse search is not configured. Add SERP_API_KEY and restart StudyLib."
    )

    for path, handler, body in (
        (
            "/api/browse/search",
            flask_app.browse_search,
            {
                "query": "archive",
                "source": "wikipedia",
                "num_results": 10,
            },
        ),
        (
            "/api/browse/search-all",
            flask_app.browse_search_all,
            {
                "query": "archive",
                "sources": ["wikipedia"],
                "num_results": 10,
            },
        ),
    ):
        with flask_app.app.test_request_context(path, method="POST", json=body):
            flask_app.session["user_id"] = 4
            response, status = handler()

        assert status == 503
        assert response.get_json() == {"status": False, "error": expected_error}


def test_browse_search_all_returns_partial_serpapi_results_with_safe_errors(
    monkeypatch,
):
    import app as flask_app

    provider_detail = "private-provider-detail"

    def fake_serp(_query, _num_results, source, _filters, *, user_id):
        assert user_id == 5
        if source == "pubmed":
            raise search.SerpApiProviderError(provider_detail)
        return [
            {
                "source_name": "wikipedia",
                "source_id": "wiki-1",
                "source_url": "https://en.wikipedia.org/wiki/Archive",
                "title": "Archive",
            }
        ]

    monkeypatch.setattr(flask_app.search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(flask_app.search, "browse_serpapi_search", fake_serp)

    with flask_app.app.test_request_context(
        "/api/browse/search-all",
        method="POST",
        json={
            "query": "archive",
            "sources": ["wikipedia", "pubmed"],
            "num_results": 10,
        },
    ):
        flask_app.session["user_id"] = 5
        response = flask_app.browse_search_all()

    payload = response.get_json()
    assert payload["status"] is True
    assert [item["title"] for item in payload["results"]] == ["Archive"]
    assert payload["source_errors"] == {"pubmed": "SerpAPI search failed"}
    assert provider_detail not in str(payload)


def test_browse_server_deadline_leaves_margin_for_browser_response(monkeypatch):
    import app as flask_app

    observed_timeouts = []
    real_wait = flask_app.concurrent.futures.wait

    def recording_wait(futures, timeout):
        observed_timeouts.append(timeout)
        return real_wait(futures, timeout=timeout)

    monkeypatch.setattr(flask_app.search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(
        flask_app.search,
        "browse_serpapi_search",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(flask_app.concurrent.futures, "wait", recording_wait)

    with flask_app.app.test_request_context(
        "/api/browse/search-all",
        method="POST",
        json={"query": "archive", "sources": ["wikipedia"]},
    ):
        flask_app.session["user_id"] = 5
        response = flask_app.browse_search_all()

    assert response.get_json()["status"] is True
    assert observed_timeouts == [25]


def test_browse_search_all_returns_safe_error_when_every_serpapi_source_fails(
    monkeypatch,
):
    import app as flask_app

    monkeypatch.setattr(flask_app.search, "SERP_API_KEY", "serp-test-key")
    monkeypatch.setattr(
        flask_app.search,
        "browse_serpapi_search",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            search.SerpApiProviderError("private-provider-detail")
        ),
    )

    with flask_app.app.test_request_context(
        "/api/browse/search-all",
        method="POST",
        json={
            "query": "archive",
            "sources": ["wikipedia", "pubmed"],
            "num_results": 10,
        },
    ):
        flask_app.session["user_id"] = 6
        response, status = flask_app.browse_search_all()

    payload = response.get_json()
    assert status == 502
    assert payload["status"] is False
    assert payload["error"] == "Browse search could not reach SerpAPI. Try again shortly."
    assert "private-provider-detail" not in str(payload)


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
    monkeypatch.setattr(search, "GOOGLE_BOOKS_API_KEY", "")

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

    def fake_get_or_create_item(item_data, user_id, add_to_recent_search):
        assert (user_id, add_to_recent_search) == (9, True)
        if item_data.get("source_id") == "existing-volume":
            return dict(existing_record)
        created_payloads.append(dict(item_data))
        return {"id": 22, **item_data}

    monkeypatch.setattr(search.requests, "get", fake_get)
    monkeypatch.setattr(search, "GOOGLE_BOOKS_API_KEY", "")
    monkeypatch.setattr(search.whitelist, "is_allowed", lambda _url: True)
    monkeypatch.setattr(search.db, "get_or_create_item", fake_get_or_create_item)

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
    monkeypatch.setattr(search.db, "get_search_cache", lambda key: None)
    monkeypatch.setattr(search.db, "get_or_create_item", lambda item_data, _user_id, _add_to_recent_search: {"id": 0, **item_data})


def _custom_search_items(domain, start, count):
    return [
        {
            "link": f"https://{domain}/result-{index}",
            "title": f"Result {index}",
            "snippet": f"Snippet {index}",
        }
        for index in range(start, start + count)
    ]


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
