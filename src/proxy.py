from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from readability import Document

import src.whitelist as whitelist

DEFAULT_HEADERS = {
    "User-Agent": "StudyLib/1.0 (Academic Research Assistant)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RESPONSE_BYTES = 2 * 1024 * 1024

BOOKS_DOMAIN = "books.google.com"

SKIP_DOMAINS = frozenset({
    "www.jstor.org",
    "www.sciencedirect.com",
    "link.springer.com",
})

_STRIP_TAGS = (
    "script",
    "noscript",
    "iframe",
    "frame",
    "frameset",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "object",
    "embed",
    "applet",
    "template",
    "meta",
    "style",
    "svg",
    "math",
    "nav",
    "header",
    "footer",
)

_STRIP_ATTRS = frozenset({
    "action",
    "autofocus",
    "contenteditable",
    "formaction",
    "ping",
    "srcdoc",
    "srcset",
    "style",
    "xlink:href",
})

_URL_ATTRS = frozenset({"href", "src", "poster"})

_PAYWALL_PHRASES = (
    "paywall",
    "access denied",
    "subscription required",
    "subscribe to continue",
    "sign in to continue",
    "log in to continue",
    "please sign in",
    "please login",
    "sign in to view",
    "this content is for subscribers only",
    "join now to read",
    "subscription required to view",
    "you need to sign in",
)

_CLOUDFLARE_PHRASES = (
    "checking your browser before accessing",
    "just a moment",
    "cf-ray",
    "cloudflare",
)


def _make_absolute(raw_value, base_url):
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None
    value = raw_value.strip()
    if value.lower().startswith("javascript:") or value.lower().startswith("data:"):
        return None
    try:
        absolute = urljoin(base_url, value)
    except (TypeError, ValueError):
        return None
    if absolute.startswith(("http://", "https://", "/")):
        return absolute
    return None


def _sanitize_soup(soup, base_url):
    for tag in soup(_STRIP_TAGS):
        if tag.parent is not None:
            tag.decompose()

    for tag in soup.find_all(True):
        for attr_name in list(tag.attrs):
            lower = attr_name.lower()
            if lower.startswith("on") or lower in _STRIP_ATTRS:
                del tag.attrs[attr_name]
                continue
            if lower in _URL_ATTRS:
                safe = _make_absolute(tag.attrs.get(attr_name), base_url)
                if safe is not None:
                    tag.attrs[attr_name] = safe
                else:
                    del tag.attrs[attr_name]

        if tag.name == "a" and tag.get("href"):
            tag["target"] = "_blank"
            tag["rel"] = "noopener noreferrer"


def fetch_source(url):
    if not whitelist.is_allowed(url):
        raise ValueError("URL not allowed")

    domain = whitelist.get_domain(url)

    if domain == BOOKS_DOMAIN:
        return {
            "status": False,
            "error": "Google Books previews use the native viewer.",
            "fallback_url": url,
        }

    if domain in SKIP_DOMAINS:
        display_name = whitelist.get_display_name_for_domain(domain) or domain
        return {
            "status": False,
            "error": f"{display_name} content requires a subscription. Open in a new tab.",
            "html": "",
            "text": "",
            "title": display_name,
            "url": url,
            "domain": domain,
            "mode": "reader",
            "fallback_url": url,
        }

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
    except requests.Timeout:
        return {"status": False, "error": "Request timed out"}
    except requests.RequestException:
        return {"status": False, "error": "Failed to fetch source"}

    if resp.status_code != 200:
        if resp.status_code in (403, 429):
            return {
                "status": False,
                "error": "Source blocked by the remote site. Open it directly in a new tab.",
                "fallback_url": url,
            }
        return {"status": False, "error": "Failed to load source"}

    if len(resp.content) > MAX_RESPONSE_BYTES:
        return {"status": False, "error": "Source response was too large to preview"}

    final_url = resp.url
    final_domain = whitelist.get_domain(final_url)

    try:
        doc = Document(resp.text)
        readable_html = doc.summary()
        title = doc.title() or ""
    except Exception:
        return {"status": False, "error": "Failed to parse source content"}

    soup = BeautifulSoup(readable_html, "html.parser")
    _sanitize_soup(soup, final_url)

    base_tag = soup.new_tag("base", href=final_url, target="_blank")
    html_parts = [str(base_tag)]
    if soup.body:
        html_parts.extend(str(child) for child in soup.body.contents)
    else:
        html_parts.append(str(soup))
    html = "".join(html_parts)

    text = soup.get_text(separator=" ", strip=True)

    # Wikipedia pages are never paywalled / Cloudflare-blocked — skip those checks.
    if final_domain and not final_domain.endswith("wikipedia.org"):
        cleaned = text.lower()
        if any(phrase in cleaned for phrase in _CLOUDFLARE_PHRASES):
            return {
                "status": False,
                "error": "Source blocked by remote site protection. Open it directly in a new tab.",
                "fallback_url": url,
            }
        if any(phrase in cleaned for phrase in _PAYWALL_PHRASES):
            return {
                "status": False,
                "error": "This source could not be loaded \u2014 it may be paywalled or require login.",
                "fallback_url": url,
            }

    return {
        "status": True,
        "html": html,
        "text": text,
        "title": title,
        "url": final_url,
        "domain": final_domain,
        "mode": "reader",
    }
