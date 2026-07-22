from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

import src.proxy as proxy

PUBLIC_URL = "https://en.wikipedia.org/wiki/Sample"
EXPECTED_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class FakeResponse:
    def __init__(self, content=b"", status_code=200, url=PUBLIC_URL):
        self.content = content
        self.status_code = status_code
        self.url = url

    @property
    def text(self):
        return self.content.decode("utf-8", errors="replace")


def _simple_html(title="Test Page", body="<p>Hello world</p>"):
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>".encode()


class TestFetchSourceBasic:

    def test_returns_readable_content_and_title(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "en.wikipedia.org")
        html = _simple_html("Sample Article", "<article><p>Main text here.</p></article>")
        monkeypatch.setattr(proxy.requests, "get", lambda url, headers, timeout: FakeResponse(html))

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is True
        assert result["mode"] == "reader"
        assert "Main text here" in result["html"]
        assert "Sample Article" in result.get("title", "")
        assert "Main text here" in result["text"]

    def test_rejects_non_whitelisted_url(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: False)

        with pytest.raises(ValueError, match="URL not allowed"):
            proxy.fetch_source("https://evil.test/page")

    def test_google_books_bypasses_fetch(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "books.google.com")
        mock_get = MagicMock()
        monkeypatch.setattr(proxy.requests, "get", mock_get)

        result = proxy.fetch_source("https://books.google.com/books?id=abc123")

        mock_get.assert_not_called()
        assert result["status"] is False
        assert "native viewer" in result["error"].lower()
        assert result["fallback_url"] is not None

    @pytest.mark.parametrize("domain", ["www.jstor.org", "www.sciencedirect.com", "link.springer.com"])
    def test_subscription_sites_return_fallback(self, monkeypatch, domain):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: domain)
        monkeypatch.setattr(proxy.whitelist, "get_display_name_for_domain", lambda _url: domain)
        mock_get = MagicMock()
        monkeypatch.setattr(proxy.requests, "get", mock_get)

        result = proxy.fetch_source(f"https://{domain}/article")

        mock_get.assert_not_called()
        assert result["status"] is False
        assert "subscription" in result["error"].lower()
        assert "fallback_url" in result

    def test_non_200_status(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "example.org")
        monkeypatch.setattr(
            proxy.requests,
            "get",
            lambda url, headers, timeout: FakeResponse(b"", status_code=404),
        )

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is False
        assert "Failed to load source" in result["error"]

    def test_403_returns_fallback_url(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "example.org")
        monkeypatch.setattr(
            proxy.requests,
            "get",
            lambda url, headers, timeout: FakeResponse(b"", status_code=403),
        )

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is False
        assert "blocked" in result["error"].lower()
        assert result.get("fallback_url")

    def test_timeout(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "example.org")

        import requests as real_requests

        def _raise_timeout(url, headers, timeout):
            raise real_requests.Timeout()

        monkeypatch.setattr(proxy.requests, "get", _raise_timeout)

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is False
        assert "timed out" in result["error"].lower()

    def test_request_exception(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "example.org")

        import requests as real_requests

        def _raise_error(url, headers, timeout):
            raise real_requests.ConnectionError("connection refused")

        monkeypatch.setattr(proxy.requests, "get", _raise_error)

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is False
        assert "Failed to fetch source" in result["error"]


class TestFetchSourceSize:
    def test_rejects_overly_large_response(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "example.org")
        monkeypatch.setattr(
            proxy.requests,
            "get",
            lambda url, headers, timeout: FakeResponse(b"x" * (EXPECTED_MAX_RESPONSE_BYTES + 1)),
        )
        assert getattr(proxy, "MAX_RESPONSE_BYTES", None) == EXPECTED_MAX_RESPONSE_BYTES

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is False
        assert "too large" in result["error"].lower()


class TestSanitization:
    def test_strips_active_tags_and_event_handlers(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "en.wikipedia.org")
        html = b"""<html><head><title>Test</title></head><body>
            <script>alert(1)</script>
            <form action="/submit"><button>Go</button></form>
            <iframe src="https://evil.test"></iframe>
            <div onclick="alert(1)" style="color:red">Danger</div>
            <a href="/wiki/Safe">Safe link</a>
        </body></html>"""
        monkeypatch.setattr(proxy.requests, "get", lambda url, headers, timeout: FakeResponse(html))

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is True
        soup = BeautifulSoup(result["html"], "html.parser")
        assert not soup.find_all(["script", "style", "form", "button", "iframe"])
        assert not any(
            name.lower().startswith("on") or name.lower() in {"style", "srcdoc"}
            for tag in soup.find_all(True)
            for name in tag.attrs
        )

    def test_safe_link_gets_target_blank_and_rel(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "en.wikipedia.org")
        html = b"<html><body><a href=\"/wiki/Science\">Science</a></body></html>"
        monkeypatch.setattr(proxy.requests, "get", lambda url, headers, timeout: FakeResponse(html))

        result = proxy.fetch_source(PUBLIC_URL)

        soup = BeautifulSoup(result["html"], "html.parser")
        link = soup.find("a")
        assert link is not None
        assert link["target"] == "_blank"
        assert "noopener" in link.get("rel", [])

    def test_strips_javascript_hrefs(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "en.wikipedia.org")
        html = b"<html><body><a href=\"javascript:alert(1)\">Evil</a></body></html>"
        monkeypatch.setattr(proxy.requests, "get", lambda url, headers, timeout: FakeResponse(html))

        result = proxy.fetch_source(PUBLIC_URL)

        soup = BeautifulSoup(result["html"], "html.parser")
        link = soup.find("a")
        assert link is not None
        assert link.get("href") is None


class TestPaywallAndCloudflare:

    def test_detects_paywall_phrases(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "www.britannica.com")
        html = b"<html><body><p>Please subscribe to continue reading this article.</p></body></html>"
        monkeypatch.setattr(proxy.requests, "get", lambda url, headers, timeout: FakeResponse(html))

        result = proxy.fetch_source("https://www.britannica.com/article")

        assert result["status"] is False
        assert "paywalled" in result["error"].lower()
        assert result.get("fallback_url")

    def test_detects_cloudflare(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "www.nationalgeographic.com")
        html = b"<html><body>Checking your browser before accessing the site. CF-RAY: abc123</body></html>"
        monkeypatch.setattr(proxy.requests, "get", lambda url, headers, timeout: FakeResponse(html))

        result = proxy.fetch_source("https://www.nationalgeographic.com/article")

        assert result["status"] is False
        assert "blocked" in result["error"].lower()
        assert result.get("fallback_url")

    def test_wikipedia_skips_paywall_checks(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "en.wikipedia.org")
        # Page contains a paywall phrase but is Wikipedia — should still succeed.
        html = b"<html><head><title>Paywall Article</title></head><body><p>Wikipedia page about subscription required concepts.</p></body></html>"
        monkeypatch.setattr(proxy.requests, "get", lambda url, headers, timeout: FakeResponse(html))

        result = proxy.fetch_source("https://en.wikipedia.org/wiki/Paywall")

        assert result["status"] is True
        assert "subscription required" in result["text"].lower()


class TestReadabilityIntegration:

    def test_extracts_main_content_ignoring_nav_and_sidebar(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "www.britannica.com")
        html = b"""<html><head><title>Encyclopedia Entry</title></head><body>
            <nav>Home | About | Contact</nav>
            <article><p>This is the real article text that should be extracted.</p></article>
            <aside>Sidebar with ads</aside>
            <footer>Copyright 2026</footer>
        </body></html>"""
        monkeypatch.setattr(proxy.requests, "get", lambda url, headers, timeout: FakeResponse(html))

        result = proxy.fetch_source("https://www.britannica.com/entry")

        assert result["status"] is True
        assert "real article text" in result["html"]
        # readability strips nav/sidebar/footer
        assert "Home | About" not in result["html"]
        assert "Sidebar with ads" not in result["html"]
        assert "Copyright" not in result["html"]
