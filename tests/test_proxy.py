import socket
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import urllib3.connection
from bs4 import BeautifulSoup
import src.proxy as proxy


PUBLIC_IP = "93.184.216.34"
EXPECTED_MAX_REDIRECT_HOPS = 5
EXPECTED_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
EXPECTED_RESPONSE_CHUNK_BYTES = 64 * 1024


def test_proxy_transport_dependencies_match_pinned_adapter_contract():
    requirement_lines = {
        line.strip()
        for line in (Path(__file__).parents[1] / "requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "requests>=2.32.3" in requirement_lines
    assert "urllib3>=1.24,<3" in requirement_lines


def _peer_raw(peer_ip):
    class PeerSocket:
        def getpeername(self):
            return (peer_ip, 443)

    class Connection:
        sock = PeerSocket()

    class Raw:
        _connection = Connection()

    return Raw()


class FakeResponse:
    def __init__(
        self,
        content=b"",
        *,
        status_code=200,
        headers=None,
        chunks=None,
        peer_ip=PUBLIC_IP,
    ):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks
        self.closed = False
        if peer_ip is not None:
            self.raw = _peer_raw(peer_ip)

    def iter_content(self, chunk_size=65536):
        if self._chunks is not None:
            yield from self._chunks
            return
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset : offset + chunk_size]

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    def fake_getaddrinfo(_host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_IP, port))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)


@pytest.fixture
def mock_session(monkeypatch):
    session = MagicMock()
    session.trust_env = True
    session_factory = MagicMock(return_value=session)
    session.factory = session_factory
    monkeypatch.setattr(proxy.requests, "Session", session_factory)
    # Keeps the pre-Session implementation safely mocked for the RED run.
    monkeypatch.setattr(proxy.requests, "get", session.get)
    return session


def test_proxy_allowed_url(mock_session):
    mock_response = FakeResponse(b"<html><body>Test content</body></html>")
    mock_session.get.return_value = mock_response
    
    result = proxy.fetch_source("https://en.wikipedia.org/test")
    assert result["status"] == True
    assert "Test content" in result["html"]
    assert result["mode"] == "iframe"
    assert mock_session.get.call_args.args == (f"https://{PUBLIC_IP}/test",)
    assert mock_session.get.call_args.kwargs["headers"]["Host"] == "en.wikipedia.org"
    assert mock_session.get.call_args.kwargs["allow_redirects"] is False
    assert mock_session.get.call_args.kwargs["stream"] is True
    assert mock_response.closed is True


def test_pinned_https_adapter_preserves_sni_and_certificate_hostname():
    adapter_class = getattr(proxy, "_PinnedAddressAdapter", None)
    assert adapter_class is not None
    adapter = adapter_class()
    try:
        adapter.pin_hostname("en.wikipedia.org")
        request = proxy.requests.Request(
            "GET",
            f"https://{PUBLIC_IP}/archive",
            headers={"Host": "en.wikipedia.org"},
        ).prepare()

        host_params, pool_kwargs = adapter.build_connection_pool_key_attributes(
            request,
            verify=True,
        )

        assert host_params["host"] == PUBLIC_IP
        assert pool_kwargs["server_hostname"] == "en.wikipedia.org"
        assert pool_kwargs["assert_hostname"] == "en.wikipedia.org"
        assert pool_kwargs["cert_reqs"] == "CERT_REQUIRED"
    finally:
        adapter.close()


def test_proxy_uses_identity_encoding_with_environment_isolated_session(mock_session):
    mock_session.get.return_value = FakeResponse(
        b"<html><body>Isolated</body></html>"
    )

    result = proxy.fetch_source("https://en.wikipedia.org/test")

    assert result["status"] is True
    mock_session.factory.assert_called_once_with()
    assert mock_session.trust_env is False
    assert mock_session.get.call_args.kwargs["headers"]["Accept-Encoding"] == "identity"
    mock_session.close.assert_called_once_with()


def test_proxy_closes_session_when_pinned_adapter_mount_fails(mock_session):
    mock_session.mount.side_effect = RuntimeError("mount failed")

    result = proxy.fetch_source("https://en.wikipedia.org/test")

    assert result["status"] is False
    mock_session.close.assert_called_once_with()
    mock_session.get.assert_not_called()


def test_proxy_keeps_simple_response_mocks_with_peer_metadata_testable(mock_session):
    class ContentOnlyResponse:
        status_code = 200
        headers = {}
        content = b"<html><body>Simple mock</body></html>"
        raw = _peer_raw(PUBLIC_IP)

        def close(self):
            pass

    mock_session.get.return_value = ContentOnlyResponse()

    result = proxy.fetch_source("https://en.wikipedia.org/test")

    assert result["status"] is True
    assert "Simple mock" in result["html"]

def test_proxy_reader_mode_for_nhs(mock_session):
    mock_response = FakeResponse(b"<html><head><title>NHS</title></head><body><div>Patient info</div></body></html>")
    mock_session.get.return_value = mock_response

    result = proxy.fetch_source("https://www.nhs.uk/article")
    assert result["status"] == True
    assert result["mode"] == "reader"
    assert "Patient info" in result["html"]


def test_proxy_strips_active_markup_and_preserves_safe_direct_links(mock_session):
    mock_response = FakeResponse(b"""
        <html>
          <head>
            <base href="javascript:alert(1)">
            <title>Archive</title>
            <style>@import url(https://evil.test/theme.css); body { background: url(https://evil.test/pixel) }</style>
            <link rel="stylesheet" href="https://evil.test/theme.css">
            <link rel="alternate stylesheet" href="https://evil.test/alternate.css">
            <link rel="preload" as="style" href="https://evil.test/preloaded.css">
          </head>
          <body onload="alert(1)">
            <script>alert(1)</script>
            <object data="https://evil.test/plugin"></object>
            <embed src="https://evil.test/plugin">
            <form action="https://evil.test/submit"><button>Send</button></form>
            <a id="bad" href="javascript:alert(1)" onclick="alert(1)">Bad</a>
            <a id="safe" href="/wiki/Safe" style="background:url(javascript:alert(1))">Safe</a>
            <img src="/image.png" onerror="alert(1)" srcdoc="<script>alert(1)</script>">
          </body>
        </html>
    """)
    mock_session.get.return_value = mock_response

    result = proxy.fetch_source("https://en.wikipedia.org/wiki/Archive")

    soup = BeautifulSoup(result["html"], "html.parser")
    assert result["status"] is True
    assert not soup.find_all(["script", "style", "object", "embed", "form", "button"])
    assert not soup.select('link[rel~="stylesheet"]')
    assert not soup.select('link[as="style"]')
    assert not [
        name
        for tag in soup.find_all(True)
        for name in tag.attrs
        if name.lower().startswith("on") or name.lower() in {"style", "srcdoc"}
    ]
    assert soup.select_one("#bad").get("href") is None
    safe_link = soup.select_one("#safe")
    assert safe_link.get("href") == "https://en.wikipedia.org/wiki/Safe"
    assert safe_link.get("target") == "_blank"
    assert set(safe_link.get("rel", [])) == {"noopener", "noreferrer"}
    assert soup.select_one("img").get("src") == "https://en.wikipedia.org/image.png"
    base = soup.select_one("base")
    assert base.get("href") == "https://en.wikipedia.org/wiki/Archive"
    assert base.get("target") == "_blank"

def test_proxy_google_books_uses_native_viewer_without_remote_fetch(mock_session):
    source_url = "https://books.google.com/books?id=test"

    result = proxy.fetch_source(source_url)

    mock_session.get.assert_not_called()
    assert result["status"] is False
    assert "html" not in result
    assert result["fallback_url"] == source_url
    assert "native viewer" in result["error"].lower()

def test_proxy_not_allowed(mock_session):
    with pytest.raises(ValueError):
        proxy.fetch_source("https://example.com/test")


def test_proxy_non_200(mock_session):
    mock_response = FakeResponse(status_code=404)
    mock_session.get.return_value = mock_response
    
    result = proxy.fetch_source("https://en.wikipedia.org/test")
    assert result["status"] == False
    assert "Failed to load source" in result["error"]


def test_proxy_rejects_direct_private_literal_before_fetch(mock_session, monkeypatch):
    monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda _host, port, *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", port))
        ],
    )

    with pytest.raises(ValueError, match="public network"):
        proxy.fetch_source("http://127.0.0.1/latest/meta-data")

    mock_session.get.assert_not_called()


def test_proxy_pins_prevalidated_ip_before_any_transport_connect(monkeypatch):
    dns_calls = []
    contacted_addresses = []

    def rebinding_dns(host, port, *args, **kwargs):
        assert host == "en.wikipedia.org"
        dns_calls.append(host)
        address = PUBLIC_IP if len(dns_calls) == 1 else "127.0.0.1"
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))
        ]

    def abort_before_send(address, *args, **kwargs):
        host, port = address
        if host == "en.wikipedia.org":
            rebound = rebinding_dns(host, port)[0][4][0]
            contacted_addresses.append(rebound)
        else:
            contacted_addresses.append(host)
        raise OSError("stop before transport sends bytes")

    monkeypatch.setattr(socket, "getaddrinfo", rebinding_dns)
    monkeypatch.setattr(
        urllib3.connection.connection,
        "create_connection",
        abort_before_send,
    )

    result = proxy.fetch_source("https://en.wikipedia.org/archive")

    assert result["status"] is False
    assert dns_calls == ["en.wikipedia.org"]
    assert contacted_addresses == [PUBLIC_IP]
    assert "127.0.0.1" not in contacted_addresses


def test_proxy_rejects_redirect_to_private_target(mock_session, monkeypatch):
    monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)

    def resolving(host, port, *args, **kwargs):
        address = "127.0.0.1" if host == "private.test" else PUBLIC_IP
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", resolving)
    redirect = FakeResponse(
        status_code=302,
        headers={"Location": "https://private.test/metadata"},
    )
    mock_session.get.return_value = redirect

    with pytest.raises(ValueError, match="public network"):
        proxy.fetch_source("https://en.wikipedia.org/start")

    assert mock_session.get.call_count == 1
    assert redirect.closed is True


@pytest.mark.parametrize(
    "addresses",
    [
        ["10.0.0.8"],
        [PUBLIC_IP, "169.254.169.254"],
        ["2001:db8::1"],
    ],
)
def test_proxy_rejects_private_reserved_or_mixed_dns_answers(
    mock_session, monkeypatch, addresses
):
    monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)

    def resolving(_host, port, *args, **kwargs):
        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                (address, port),
            )
            for address in addresses
        ]

    monkeypatch.setattr(socket, "getaddrinfo", resolving)

    with pytest.raises(ValueError, match="public network"):
        proxy.fetch_source("https://en.wikipedia.org/archive")

    mock_session.get.assert_not_called()


@pytest.mark.parametrize(
    "address",
    [
        "224.0.0.1",
        "64:ff9b::a00:8",
        "64:ff9b:1::a00:8",
    ],
)
def test_proxy_rejects_multicast_and_nat64_private_dns_answers(
    mock_session, monkeypatch, address
):
    monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda _host, port, *args, **kwargs: [
            (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))
        ],
    )

    with pytest.raises(ValueError, match="public network"):
        proxy.fetch_source("https://en.wikipedia.org/archive")

    mock_session.get.assert_not_called()


def test_proxy_rejects_ipv6_site_local_before_session_get(mock_session, monkeypatch):
    monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda _host, port, *args, **kwargs: [
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("fec0::1", port),
            )
        ],
    )

    with pytest.raises(ValueError) as error:
        proxy.fetch_source("https://en.wikipedia.org/archive")

    mock_session.get.assert_not_called()
    assert "public network" in str(error.value)


def test_proxy_stops_after_documented_redirect_hop_limit(mock_session, monkeypatch):
    monkeypatch.setattr(proxy.whitelist, "is_allowed", lambda _url: True)
    assert getattr(proxy, "MAX_REDIRECT_HOPS", None) == EXPECTED_MAX_REDIRECT_HOPS
    responses = [
        FakeResponse(status_code=302, headers={"Location": f"/hop-{index + 1}"})
        for index in range(EXPECTED_MAX_REDIRECT_HOPS + 1)
    ]
    mock_session.get.side_effect = responses

    result = proxy.fetch_source("https://en.wikipedia.org/hop-0")

    assert result["status"] is False
    assert "redirect" in result["error"].lower()
    assert mock_session.get.call_count == EXPECTED_MAX_REDIRECT_HOPS + 1
    assert all(response.closed for response in responses)


def test_proxy_rejects_response_larger_than_byte_ceiling(mock_session):
    assert getattr(proxy, "MAX_RESPONSE_BYTES", None) == EXPECTED_MAX_RESPONSE_BYTES
    response = FakeResponse(
        chunks=[b"a" * EXPECTED_RESPONSE_CHUNK_BYTES]
        * ((EXPECTED_MAX_RESPONSE_BYTES // EXPECTED_RESPONSE_CHUNK_BYTES) + 2)
    )
    mock_session.get.return_value = response

    result = proxy.fetch_source("https://en.wikipedia.org/archive")

    assert result["status"] is False
    assert "too large" in result["error"].lower()
    assert response.closed is True


def test_proxy_rejects_connected_peer_outside_resolved_dns_answers(mock_session):
    mock_session.get.return_value = FakeResponse(
        b"<html><body>Archive</body></html>",
        peer_ip="8.8.8.8",
    )

    with pytest.raises(ValueError, match="connected peer"):
        proxy.fetch_source("https://en.wikipedia.org/archive")


def test_proxy_rejects_response_when_connected_peer_is_unavailable(mock_session):
    mock_session.get.return_value = FakeResponse(
        b"<html><body>Archive</body></html>",
        peer_ip=None,
    )

    with pytest.raises(ValueError, match="connected peer"):
        proxy.fetch_source("https://en.wikipedia.org/archive")


def test_proxy_rejects_non_identity_content_encoding(mock_session):
    response = FakeResponse(
        b"decoded bytes can exceed the compressed wire size",
        headers={"Content-Encoding": "gzip"},
    )
    mock_session.get.return_value = response

    result = proxy.fetch_source("https://en.wikipedia.org/archive")

    assert result["status"] is False
    assert "encoding" in result["error"].lower()
    assert response.closed is True
