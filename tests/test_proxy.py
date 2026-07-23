from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

import src.proxy as proxy

PUBLIC_URL = "https://en.wikipedia.org/wiki/Sample"


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

    def test_returns_full_html_with_base_tag(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "en.wikipedia.org")
        html = _simple_html("Sample Article", "<article><p>Main text here.</p></article>")
        monkeypatch.setattr(proxy.requests, "get", lambda url, timeout, headers=None: FakeResponse(html))

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is True
        assert result["mode"] == "iframe"
        assert "Main text here" in result["html"]
        assert result["title"] == "Sample Article"
        assert "Main text here" in result["text"]

    def test_injects_base_tag_in_head(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "en.wikipedia.org")
        html = b"<html><head><title>Test</title></head><body><img src=\"/images/logo.png\"></body></html>"
        monkeypatch.setattr(proxy.requests, "get", lambda url, timeout, headers=None: FakeResponse(html, url="https://en.wikipedia.org/wiki/Test"))

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is True
        soup = BeautifulSoup(result["html"], "html.parser")
        base = soup.head.find("base")
        assert base is not None
        assert base["href"] == "https://en.wikipedia.org/wiki/Test"
        assert base["target"] == "_blank"

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
            lambda url, timeout, headers=None: FakeResponse(b"", status_code=404),
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
            lambda url, timeout, headers=None: FakeResponse(b"", status_code=403),
        )

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is False
        assert "blocked" in result["error"].lower()
        assert result.get("fallback_url")

    def test_timeout(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "example.org")

        import requests as real_requests

        def _raise_timeout(url, timeout, headers=None):
            raise real_requests.Timeout()

        monkeypatch.setattr(proxy.requests, "get", _raise_timeout)

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is False
        assert "timed out" in result["error"].lower()

    def test_request_exception(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "example.org")

        import requests as real_requests

        def _raise_error(url, timeout, headers=None):
            raise real_requests.ConnectionError("connection refused")

        monkeypatch.setattr(proxy.requests, "get", _raise_error)

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is False
        assert "Failed to fetch source" in result["error"]


class TestSanitization:
    def test_strips_executable_tags(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "en.wikipedia.org")
        html = b"""<html><head><title>Test</title></head><body>
            <script>alert(1)</script>
            <form action="/submit"><button>Go</button></form>
            <iframe src="https://evil.test"></iframe>
            <input type="text" name="query">
            <embed src="https://evil.test/flash">
            <p>Legitimate paragraph</p>
        </body></html>"""
        monkeypatch.setattr(proxy.requests, "get", lambda url, timeout, headers=None: FakeResponse(html))

        result = proxy.fetch_source(PUBLIC_URL)

        assert result["status"] is True
        soup = BeautifulSoup(result["html"], "html.parser")
        assert not soup.find_all(["script", "form", "button", "iframe", "input", "embed"])
        assert soup.find("p") is not None

    def test_preserves_css_styles(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "www.nationalgeographic.com")
        html = b"""<html><head>
            <link rel="stylesheet" href="/css/main.css">
            <style>body { color: #333; font-family: serif; }</style>
        </head><body>
            <div style="background: #f0f0f0; border: 1px solid #ccc;">Colored content</div>
        </body></html>"""
        monkeypatch.setattr(proxy.requests, "get", lambda url, timeout, headers=None: FakeResponse(html))

        result = proxy.fetch_source(PUBLIC_URL)

        soup = BeautifulSoup(result["html"], "html.parser")
        assert soup.find("style") is not None
        assert soup.find("link", rel="stylesheet") is not None
        div = soup.find("div")
        assert div is not None
        assert div.get("style") is not None
        assert "background" in div["style"]

    def test_preserves_nav_and_header_structure(self, monkeypatch):
        monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
        monkeypatch.setattr(proxy.whitelist, "get_domain", lambda _url: "www.britannica.com")
        html = b"""<html><head><title>Encyclopedia</title></head><body>
            <header class="site-header"><h1>Encyclopedia Britannica</h1></header>
            <nav class="breadcrumbs"><a href="/">Home</a> &gt; <a href="/science">Science</a></nav>
            <article><p>Article content.</p></article>
            <footer><span>Copyright 2026</span></footer>
        </body></html>"""
        monkeypatch.setattr(proxy.requests, "get", lambda url, timeout, headers=None: FakeResponse(html))

        result = proxy.fetch_source(PUBLIC_URL)

        soup = BeautifulSoup(result["html"], "html.parser")
        assert soup.find("header") is not None
        assert soup.find("nav") is not None
        assert soup.find("footer") is not None
        assert soup.find("article") is not None
        assert "Article content" in result["text"]
