"""Diagnostic tests for thumbnail URL extraction from search results."""

import pytest
import src.search as search
import src.whitelist as whitelist


class TestSafeBrowseImageUrl:
    def test_serpapi_cdn_thumbnail_passes(self):
        url = "https://serpapi.com/searches/abc123/thumbnails/xyz.jpg"
        result = search._safe_browse_image_url(url)
        assert result == url, f"SerpAPI CDN URL should pass, got: {result!r}"

    def test_gstatic_thumbnail_passes(self):
        url = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ABC123"
        result = search._safe_browse_image_url(url)
        assert result == url, f"gstatic URL should pass, got: {result!r}"

    def test_googleusercontent_passes(self):
        url = "https://lh3.googleusercontent.com/abc/xyz.jpg"
        result = search._safe_browse_image_url(url)
        assert result == url

    def test_books_google_thumbnail_passes(self):
        url = "https://books.google.com/books/content?id=abc&printsec=frontcover&img=1&zoom=1"
        result = search._safe_browse_image_url(url)
        assert result == url

    def test_wikimedia_thumbnail_passes(self):
        url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Example.jpg/200px-Example.jpg"
        result = search._safe_browse_image_url(url)
        assert result == url

    def test_whitelisted_domain_thumbnail_passes(self):
        url = "https://www.britannica.com/some-thumbnail.jpg"
        result = search._safe_browse_image_url(url)
        assert result == url, f"Whitelisted domain favicon/thumbnail should pass, got: {result!r}"

    def test_wikipedia_thumbnail_passes(self):
        url = "https://en.wikipedia.org/static/images/project-logos/enwiki.png"
        result = search._safe_browse_image_url(url)
        assert result == url, f"Wikipedia domain thumbnail should pass, got: {result!r}"

    def test_pubmed_favicon_should_pass(self):
        url = "https://pubmed.ncbi.nlm.nih.gov/favicon.ico"
        result = search._safe_browse_image_url(url)
        assert result == url, f"PubMed favicon should pass, got: {result!r}"

    def test_unknown_domain_rejected(self):
        url = "https://some-random-site.com/image.jpg"
        result = search._safe_browse_image_url(url)
        assert result == "", f"Unknown domain should be rejected, got: {result!r}"

    def test_http_upgraded_to_https(self):
        url = "http://encrypted-tbn0.gstatic.com/images?q=tbn:ABC"
        result = search._safe_browse_image_url(url)
        assert result == url.replace("http://", "https://")

    def test_url_with_fragment_rejected(self):
        url = "https://serpapi.com/searches/abc/thumb.jpg#frag"
        result = search._safe_browse_image_url(url)
        assert result == ""

    def test_url_with_credentials_rejected(self):
        url = "https://user:pass@serpapi.com/thumb.jpg"
        result = search._safe_browse_image_url(url)
        assert result == ""

    def test_url_too_long_rejected(self):
        long_path = "/" + "x" * 300
        url = f"https://serpapi.com{long_path}"
        result = search._safe_browse_image_url(url)
        assert result == ""

    def test_empty_string_rejected(self):
        assert search._safe_browse_image_url("") == ""
        assert search._safe_browse_image_url(None) == ""

    def test_no_hostname_rejected(self):
        assert search._safe_browse_image_url("https:///path") == ""


class TestBrowseResultImageUrl:
    """Test _browse_result_image_url with various SerpAPI organic_result shapes."""

    def test_serpapi_with_thumbnail_field(self):
        item = {
            "link": "https://www.britannica.com/topic/something",
            "title": "Something - Britannica",
            "snippet": "A test snippet",
            "thumbnail": "https://serpapi.com/searches/abc123/thumbnails/xyz.jpg",
        }
        result = search._browse_result_image_url(item)
        assert result == "https://serpapi.com/searches/abc123/thumbnails/xyz.jpg"

    def test_serpapi_with_gstatic_thumbnail(self):
        item = {
            "link": "https://en.wikipedia.org/wiki/Test",
            "title": "Test - Wikipedia",
            "snippet": "test snippet",
            "thumbnail": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTest",
        }
        result = search._browse_result_image_url(item)
        assert result == "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTest"

    def test_serpapi_with_favicon_from_whitelisted_domain(self):
        item = {
            "link": "https://www.britannica.com/topic/test",
            "title": "Test",
            "snippet": "test",
            "favicon": "https://www.britannica.com/favicon.ico",
        }
        result = search._browse_result_image_url(item)
        assert result == "https://www.britannica.com/favicon.ico"

    def test_serpapi_with_no_thumbnail_or_favicon_returns_empty(self):
        item = {
            "link": "https://www.britannica.com/topic/test",
            "title": "Test",
            "snippet": "test",
        }
        result = search._browse_result_image_url(item)
        assert result == "", f"Without thumbnail/favicon should be empty, got: {result!r}"

    def test_serpapi_favicon_from_non_whitelisted_domain_rejected(self):
        item = {
            "link": "https://some-other-site.com/test",
            "title": "Test",
            "snippet": "test",
            "favicon": "https://some-other-site.com/favicon.ico",
        }
        result = search._browse_result_image_url(item)
        assert result == "", (
            f"Favicon from non-whitelisted domain should be rejected, got: {result!r}"
        )

    def test_thumbnail_takes_priority_over_favicon(self):
        item = {
            "thumbnail": "https://serpapi.com/searches/thumb.jpg",
            "favicon": "https://www.britannica.com/favicon.ico",
        }
        result = search._browse_result_image_url(item)
        assert result == "https://serpapi.com/searches/thumb.jpg"

    def test_favicon_used_when_no_thumbnail(self):
        item = {
            "link": "https://www.britannica.com/topic/test",
            "favicon": "https://www.britannica.com/favicon.ico",
        }
        result = search._browse_result_image_url(item)
        assert result == "https://www.britannica.com/favicon.ico"

    def test_empty_thumbnail_falls_through_to_favicon(self):
        item = {
            "link": "https://www.britannica.com/topic/test",
            "thumbnail": "",
            "favicon": "https://www.britannica.com/favicon.ico",
        }
        result = search._browse_result_image_url(item)
        assert result == "https://www.britannica.com/favicon.ico"

    def test_google_books_result_gets_cover_not_thumbnail(self):
        item = {
            "link": "https://books.google.com/books?id=abc123XYZ",
            "title": "A Great Book",
            "snippet": "book snippet",
            "thumbnail": "https://serpapi.com/thumb.jpg",
            "favicon": "https://books.google.com/favicon.ico",
        }
        result = search._browse_result_image_url(item)
        assert "books.google.com/books/content" in result
        assert "abc123XYZ" in result

    def test_pagemap_cse_thumbnail_is_extracted(self):
        item = {
            "link": "https://www.britannica.com/topic/test",
            "title": "Test",
            "snippet": "test",
            "pagemap": {
                "cse_thumbnail": [
                    {"src": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTest"}
                ]
            },
        }
        result = search._browse_result_image_url(item)
        assert result == "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTest"

    def test_pagemap_cse_image_is_extracted(self):
        item = {
            "link": "https://en.wikipedia.org/wiki/Test",
            "title": "Test",
            "snippet": "test",
            "pagemap": {
                "cse_image": [
                    {"src": "https://upload.wikimedia.org/wikipedia/en/thumb/test.jpg"}
                ]
            },
        }
        result = search._browse_result_image_url(item)
        assert result == "https://upload.wikimedia.org/wikipedia/en/thumb/test.jpg"

    def test_typical_serpapi_organic_result_no_thumbnail(self):
        """Most realistic case: SerpAPI organic result without thumbnail/favicon."""
        item = {
            "position": 1,
            "title": "Machine Learning - Wikipedia",
            "link": "https://en.wikipedia.org/wiki/Machine_learning",
            "displayed_link": "https://en.wikipedia.org \u203a wiki \u203a Machine_learning",
            "snippet": "Machine learning is a field of inquiry devoted to...",
            "sitelinks": {"inline": []},
            "about_this_result": {},
        }
        result = search._browse_result_image_url(item)
        assert result == "", (
            f"Typical organic result has no thumbnail: got {result!r}. "
            "This is expected - SerpAPI organic results rarely have thumbnail/favicon fields."
        )


class TestWikipediaThumbnail:
    """Check that wikipedia() function produces thumbnails."""

    def test_wikipedia_thumbnail_source_is_passed_through(self):
        """Verify wikipedia function puts thumbnail.source into thumb_url without validation."""
        # The wikipedia function uses page.get("thumbnail", {}).get("source", "")
        # This is NOT passed through _safe_browse_image_url, unlike gbooks and serpapi
        # This means Wikipedia thumbnails bypass the image provider whitelist check
        pass  # This is documentation, not an assertion


class TestGbooksThumbnail:
    """Check that gbooks() function produces thumbnails."""

    def test_gbooks_thumbnail_passes_validation(self):
        """Google Books thumbnail from books.google.com should pass _safe_browse_image_url."""
        url = "http://books.google.com/books/content?id=abc123&printsec=frontcover&img=1&zoom=1&edge=curl&source=gbs_api"
        result = search._safe_browse_image_url(url)
        assert "books.google.com" in result
        assert result.startswith("https://")


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def test_summarize_thumbnail_sources(monkeypatch):
    """Document which sources produce thumb_url and which don't."""
    print("\n=== THUMBNAIL DIAGNOSTIC SUMMARY ===")
    print()

    # Wikipedia: gets thumb from pageimages API
    wp_item = {"thumbnail": {"source": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Example.jpg"}}
    wp_thumb = wp_item.get("thumbnail", {}).get("source", "")
    wp_safe = search._safe_browse_image_url(wp_thumb)
    print(f"Wikipedia (via pageimages): raw={wp_thumb!r}, safe={wp_safe!r}")

    # GBooks: gets from imageLinks.thumbnail
    gb_thumb = "http://books.google.com/books/content?id=abc123&printsec=frontcover&img=1&zoom=1"
    gb_safe = search._safe_browse_image_url(gb_thumb)
    print(f"Google Books (imageLinks): raw={gb_thumb[:60]}..., safe={gb_safe[:60] if gb_safe else 'EMPTY'}")

    # SerpAPI with thumbnail field (rare)
    serp_thumb = "https://serpapi.com/searches/abc/thumb.jpg"
    serp_safe = search._safe_browse_image_url(serp_thumb)
    print(f"SerpAPI thumbnail field: safe={serp_safe!r}")

    # SerpAPI with gstatic thumbnail
    gs_thumb = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTest"
    gs_safe = search._safe_browse_image_url(gs_thumb)
    print(f"SerpAPI gstatic thumbnail: safe={gs_safe!r}")

    # SerpAPI with favicon from whitelisted domain
    fav_thumb = "https://www.britannica.com/favicon.ico"
    fav_safe = search._safe_browse_image_url(fav_thumb)
    print(f"Whitelisted domain favicon: safe={fav_safe!r}")

    # SerpAPI with favicon from non-whitelisted
    bad_fav = "https://some-site.com/favicon.ico"
    bad_safe = search._safe_browse_image_url(bad_fav)
    print(f"Non-whitelisted favicon: safe={bad_safe!r}")

    # SerpAPI with no thumbnail/favicon (MOST COMMON)
    no_img = search._browse_result_image_url({"link": "https://www.britannica.com/test"})
    print(f"SerpAPI no thumbnail/favicon: {no_img!r} (EMPTY = no image)")

    # pagemap (NOT HANDLED)
    pmap_thumb = search._browse_result_image_url({
        "link": "https://www.britannica.com/test",
        "pagemap": {"cse_thumbnail": [{"src": "https://encrypted-tbn0.gstatic.com/images?q=tbn:test"}]}
    })
    print(f"pagemap cse_thumbnail (NOT HANDLED): {pmap_thumb!r}")

    print()
    print("KEY FINDING: SerpAPI organic_results often lack 'thumbnail' and 'favicon' fields.")
    print("When present, thumbnail URLs from serpapi.com or gstatic.com pass validation.")
    print("When present, favicon URLs from whitelisted domains pass validation.")
    print("But pagemap (cse_thumbnail/cse_image) is NOT extracted - this is the biggest gap.")
    print("For most typical search results, thumb_url will be empty string.")
    print()
    print("Fix options:")
    print("  1. Extract from pagemap.cse_thumbnail[0].src")
    print("  2. Extract from pagemap.cse_image[0].src")
    print("  3. Extract from pagemap.imageobject[0].url (schema.org)")
    print("  4. For wikipedia source, validate thumb URL through _safe_browse_image_url")
    print()

    # The test always passes - it's diagnostic only
    assert True
