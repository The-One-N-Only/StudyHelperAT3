import ipaddress
import socket

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib.parse import urljoin, urlsplit, urlunsplit
import src.whitelist as whitelist

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}
READER_DOMAINS = frozenset([
    "web.md",
    "pubmed.ncbi.nlm.nih.gov",
    "eric.ed.gov",
    "www.britannica.com",
    "www.researchgate.net",
    "www.academia.edu",
])
READER_DOMAIN_SUFFIXES = frozenset([
    ".gov.uk",
    ".nhs.uk",
    ".gov.au",
    ".ac.uk",
    ".bbc.co.uk",
])
REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})
MAX_REDIRECT_HOPS = 5
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
RESPONSE_CHUNK_BYTES = 64 * 1024
NAT64_WELL_KNOWN_PREFIX = ipaddress.ip_network("64:ff9b::/96")
NAT64_LOCAL_USE_PREFIX = ipaddress.ip_network("64:ff9b:1::/48")
ACTIVE_TAGS = (
    'script', 'noscript', 'iframe', 'frame', 'frameset', 'form', 'button',
    'input', 'select', 'textarea', 'object', 'embed', 'applet', 'template',
    'meta', 'style', 'svg', 'math', 'nav', 'header', 'footer',
)
ACTIVE_ATTRIBUTES = {
    'action', 'autofocus', 'contenteditable', 'formaction', 'ping', 'srcdoc',
    'srcset', 'style', 'xlink:href',
}
URL_ATTRIBUTES = {'href', 'src', 'poster'}


class UnsafeSourceUrl(ValueError):
    """Raised when a proxy target can reach outside the public allowlisted web."""


class ResponseTooLargeError(Exception):
    """Raised before a remote response can exceed the in-memory proxy ceiling."""


class UnsupportedContentEncodingError(Exception):
    """Raised when transparent decoding could bypass the response byte ceiling."""


class TooManyRedirectsError(Exception):
    """Raised when a source exceeds the explicit redirect-hop ceiling."""


class _PinnedAddressAdapter(HTTPAdapter):
    """Connect to a pinned IP while authenticating the original TLS hostname."""

    def __init__(self):
        self._tls_hostname = None
        super().__init__()

    def pin_hostname(self, hostname: str) -> None:
        # Adapter belongs to one fetch-local Session, so this state is never shared.
        self._tls_hostname = hostname

    def build_connection_pool_key_attributes(self, request, verify, cert=None):
        host_params, pool_kwargs = super().build_connection_pool_key_attributes(
            request,
            verify,
            cert,
        )
        if urlsplit(request.url).scheme.lower() == "https":
            if not self._tls_hostname:
                raise UnsafeSourceUrl("HTTPS source hostname was not pinned")
            pool_kwargs["server_hostname"] = self._tls_hostname
            pool_kwargs["assert_hostname"] = self._tls_hostname
        return host_params, pool_kwargs


def is_reader_domain(domain: str) -> bool:
    if domain in READER_DOMAINS:
        return True
    return any(domain.endswith(suffix) for suffix in READER_DOMAIN_SUFFIXES)


def _safe_proxy_url(value, base_url: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return ''

    try:
        absolute_url = urljoin(base_url, value.strip())
        parsed = urlsplit(absolute_url)
    except (TypeError, ValueError):
        return ''
    if parsed.scheme.lower() not in {'http', 'https'} or not parsed.hostname:
        return ''
    return absolute_url


def _public_ip_text(value) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise UnsafeSourceUrl("Source URL did not resolve to a valid IP address") from exc

    if isinstance(address, ipaddress.IPv6Address):
        if address in NAT64_LOCAL_USE_PREFIX:
            raise UnsafeSourceUrl(
                "Source URL must resolve only to public network addresses"
            )
        if address in NAT64_WELL_KNOWN_PREFIX:
            embedded_ipv4 = ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
            if not embedded_ipv4.is_global or embedded_ipv4.is_multicast:
                raise UnsafeSourceUrl(
                    "Source URL must resolve only to public network addresses"
                )

    comparable = address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) else None
    if comparable is None:
        comparable = address
    if (
        comparable.is_multicast
        or (
            isinstance(address, ipaddress.IPv6Address)
            and address.is_site_local
        )
        or not comparable.is_global
    ):
        raise UnsafeSourceUrl(
            "Source URL must resolve only to public network addresses"
        )
    return str(comparable)


def _validate_fetch_url(url: str) -> frozenset[str]:
    """Validate one redirect hop and return all allowed DNS answers."""
    if not whitelist.is_allowed(url):
        raise UnsafeSourceUrl("URL not allowed")

    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise UnsafeSourceUrl("URL must use HTTP or HTTPS")
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, UnsafeSourceUrl):
            raise
        raise UnsafeSourceUrl("URL must use HTTP or HTTPS") from exc

    try:
        answers = socket.getaddrinfo(
            parsed.hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise UnsafeSourceUrl("Source hostname could not be resolved") from exc

    addresses = set()
    for answer in answers:
        try:
            address_text = answer[4][0]
        except (IndexError, TypeError):
            raise UnsafeSourceUrl("Source hostname returned an invalid DNS answer")
        addresses.add(_public_ip_text(address_text))
    if not addresses:
        raise UnsafeSourceUrl("Source hostname returned no public network addresses")
    return frozenset(addresses)


def _select_pinned_address(addresses: frozenset[str]) -> str:
    """Choose one validated address deterministically, preferring IPv4."""
    return min(
        addresses,
        key=lambda value: (
            ipaddress.ip_address(value).version,
            int(ipaddress.ip_address(value)),
        ),
    )


def _host_header(parsed_url) -> str:
    hostname = parsed_url.hostname
    if not hostname:
        raise UnsafeSourceUrl("Source URL did not contain a hostname")
    authority = f"[{hostname}]" if ":" in hostname else hostname
    if parsed_url.port is not None:
        authority = f"{authority}:{parsed_url.port}"
    return authority


def _pinned_url(url: str, address: str) -> str:
    parsed = urlsplit(url)
    authority = f"[{address}]" if ":" in address else address
    if parsed.port is not None:
        authority = f"{authority}:{parsed.port}"
    return urlunsplit(
        (parsed.scheme, authority, parsed.path, parsed.query, parsed.fragment)
    )


def _nested_attribute(value, names):
    current = value
    for name in names:
        if current is None:
            return None
        try:
            current = getattr(current, name)
        except Exception:
            return None
    return current


def _connected_peer_ip(response) -> str | None:
    """Read Requests/urllib3 peer metadata when that implementation exposes it."""
    raw = getattr(response, "raw", None)
    socket_candidates = (
        _nested_attribute(raw, ("_connection", "sock")),
        _nested_attribute(raw, ("connection", "sock")),
        _nested_attribute(raw, ("_fp", "fp", "raw", "_sock")),
    )
    for peer_socket in socket_candidates:
        getpeername = getattr(peer_socket, "getpeername", None)
        if not callable(getpeername):
            continue
        try:
            peer = getpeername()
            if isinstance(peer, tuple) and peer:
                return str(ipaddress.ip_address(peer[0]))
        except (OSError, TypeError, ValueError):
            continue
    return None


def _verify_connected_peer(response, resolved_addresses: frozenset[str]) -> None:
    peer_ip = _connected_peer_ip(response)
    if peer_ip is None:
        raise UnsafeSourceUrl(
            "Source connected peer could not be verified against resolved addresses"
        )
    peer_ip = _public_ip_text(peer_ip)
    if peer_ip not in resolved_addresses:
        raise UnsafeSourceUrl(
            "Source connected peer did not match resolved public network addresses"
        )


def _close_response(response) -> None:
    close = getattr(response, "close", None)
    if callable(close):
        close()


def _read_response_bytes(response) -> bytes:
    headers = getattr(response, "headers", {}) or {}
    content_encoding = str(headers.get("Content-Encoding", "identity")).strip().casefold()
    if content_encoding not in {"", "identity"}:
        raise UnsupportedContentEncodingError

    content_length = headers.get("Content-Length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_RESPONSE_BYTES:
                raise ResponseTooLargeError
        except (TypeError, ValueError):
            pass

    iter_content = getattr(response, "iter_content", None)
    iterator = None
    if callable(iter_content):
        try:
            iterator = iter(iter_content(chunk_size=RESPONSE_CHUNK_BYTES))
        except TypeError:
            iterator = None
    if iterator is None:
        content = getattr(response, "content", b"")
        if not isinstance(content, bytes):
            raise TypeError("Response content must be bytes")
        if len(content) > MAX_RESPONSE_BYTES:
            raise ResponseTooLargeError
        return content

    chunks = []
    byte_count = 0
    for chunk in iterator:
        if not chunk:
            continue
        byte_count += len(chunk)
        if byte_count > MAX_RESPONSE_BYTES:
            raise ResponseTooLargeError
        chunks.append(chunk)
    return b"".join(chunks)


def _fetch_with_validated_redirects(url: str):
    session = requests.Session()
    session.trust_env = False
    try:
        pinned_adapters = {
            "http": _PinnedAddressAdapter(),
            "https": _PinnedAddressAdapter(),
        }
        for scheme, adapter in pinned_adapters.items():
            session.mount(f"{scheme}://", adapter)
        current_url = url
        for redirect_count in range(MAX_REDIRECT_HOPS + 1):
            resolved_addresses = _validate_fetch_url(current_url)
            parsed_url = urlsplit(current_url)
            pinned_address = _select_pinned_address(resolved_addresses)
            pinned_adapters[parsed_url.scheme.lower()].pin_hostname(
                parsed_url.hostname
            )
            response = session.get(
                _pinned_url(current_url, pinned_address),
                headers={**DEFAULT_HEADERS, "Host": _host_header(parsed_url)},
                timeout=10,
                allow_redirects=False,
                stream=True,
            )
            try:
                _verify_connected_peer(response, frozenset({pinned_address}))
                if response.status_code in REDIRECT_STATUS_CODES:
                    location = (getattr(response, "headers", {}) or {}).get("Location")
                    if not location:
                        return response.status_code, b"", current_url
                    if redirect_count >= MAX_REDIRECT_HOPS:
                        raise TooManyRedirectsError
                    current_url = urljoin(current_url, location)
                    continue

                content = (
                    _read_response_bytes(response)
                    if response.status_code == 200
                    else b""
                )
                return response.status_code, content, current_url
            finally:
                _close_response(response)
    finally:
        session.close()

    raise TooManyRedirectsError


def sanitize_proxy_html(soup, url: str) -> None:
    """Remove active markup and normalize navigable URLs before sandboxing."""
    for tag in soup(ACTIVE_TAGS):
        if tag.parent is not None:
            tag.decompose()
    for base_tag in soup.find_all('base'):
        base_tag.decompose()
    for link_tag in soup.find_all('link'):
        rel_values = link_tag.get('rel', [])
        if isinstance(rel_values, str):
            rel_values = rel_values.split()
        if (
            any(str(value).casefold() == 'stylesheet' for value in rel_values)
            or str(link_tag.get('as', '')).casefold() == 'style'
        ):
            link_tag.decompose()

    for tag in soup.find_all(True):
        for name in list(tag.attrs):
            normalized_name = name.lower()
            if normalized_name.startswith('on') or normalized_name in ACTIVE_ATTRIBUTES:
                del tag.attrs[name]
                continue
            if normalized_name in URL_ATTRIBUTES:
                safe_url = _safe_proxy_url(tag.attrs.get(name), url)
                if safe_url:
                    tag.attrs[name] = safe_url
                else:
                    del tag.attrs[name]

        if tag.name == 'a' and tag.get('href'):
            tag['target'] = '_blank'
            tag['rel'] = 'noopener noreferrer'


def build_reader_html(soup, url: str) -> str:
    base_tag = soup.new_tag('base', href=url, target='_blank')

    if soup.body:
        return str(base_tag) + ''.join(str(child) for child in soup.body.contents)
    return str(base_tag) + str(soup)


def fetch_source(url):
    if not whitelist.is_allowed(url):
        raise ValueError("URL not allowed")

    domain = whitelist.get_domain(url)
    if domain == "books.google.com":
        return {
            "status": False,
            "error": "Google Books previews use the native viewer.",
            "fallback_url": url,
        }
    if domain in {"www.jstor.org", "www.sciencedirect.com", "link.springer.com"}:
        return {
            "status": False,
            "error": f"{whitelist.get_display_name_for_domain(domain) or domain} content requires a subscription. Open in a new tab.",
            "html": "",
            "text": "",
            "title": whitelist.get_display_name_for_domain(domain) or domain,
            "url": url,
            "domain": domain,
            "mode": "reader",
            "fallback_url": url,
        }
    
    try:
        status_code, content, final_url = _fetch_with_validated_redirects(url)
        if status_code != 200:
            if status_code in (403, 429):
                return {"status": False, "error": "Source blocked by the remote site. Open it directly in a new tab.", "fallback_url": url}
            return {"status": False, "error": "Failed to load source"}
        
        soup = BeautifulSoup(content, 'html.parser')
        # Remove author CSS and active markup here; browser sandbox is second boundary.
        sanitize_proxy_html(soup, final_url)

        title = soup.title.string if soup.title else ""
        text = soup.get_text(separator=' ', strip=True)
        mode = 'iframe'
        domain = whitelist.get_domain(final_url)
        if is_reader_domain(domain):
            mode = 'reader'

        reader_html = ''
        if mode == 'reader':
            reader_html = build_reader_html(soup, final_url)
        else:
            if soup.head:
                base_tag = soup.new_tag('base', href=final_url, target='_blank')
                soup.head.insert(0, base_tag)

        html = reader_html if mode == 'reader' else str(soup)

        # Check for paywall using stricter phrases only, but skip Wikipedia pages.
        if domain and domain.endswith('wikipedia.org'):
            return {
                "status": True,
                "html": html,
                "text": text,
                "title": title,
                "url": final_url,
                "domain": domain,
                "mode": mode
            }

        cleaned_text = text.lower()
        if 'checking your browser before accessing' in cleaned_text or 'just a moment' in cleaned_text or 'cf-ray' in cleaned_text or 'cloudflare' in cleaned_text:
            return {"status": False, "error": "Source blocked by remote site protection. Open it directly in a new tab.", "fallback_url": url}

        paywall_indicators = [
            'paywall',
            'access denied',
            'subscription required',
            'subscribe to continue',
            'sign in to continue',
            'log in to continue',
            'please sign in',
            'please login',
            'sign in to view',
            'this content is for subscribers only',
            'join now to read',
            'subscription required to view',
            'you need to sign in'
        ]
        if any(phrase in cleaned_text for phrase in paywall_indicators):
            return {"status": False, "error": "This source could not be loaded — it may be paywalled or require login.", "fallback_url": url}
        
        return {
            "status": True,
            "html": html,
            "text": text,
            "title": title,
            "url": final_url,
            "domain": domain,
            "mode": mode
        }
    except UnsafeSourceUrl:
        raise
    except ResponseTooLargeError:
        return {"status": False, "error": "Source response was too large to preview"}
    except UnsupportedContentEncodingError:
        return {"status": False, "error": "Source response encoding was not supported"}
    except TooManyRedirectsError:
        return {"status": False, "error": "Source exceeded the redirect limit"}
    except requests.Timeout:
        return {"status": False, "error": "Request timed out"}
    except Exception:
        return {"status": False, "error": "Failed to fetch source"}
