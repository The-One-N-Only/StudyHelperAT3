from __future__ import annotations

import requests
from bs4 import BeautifulSoup

import src.whitelist as whitelist

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

PAYWALL_DOMAINS = {
    "www.jstor.org", "www.sciencedirect.com", "link.springer.com",
}

SKIP_FETCH_DOMAINS = {"books.google.com"}

LOGIN_REDIRECT_PATTERNS = [
    "/login", "/signin", "/auth", "/account", "/subscription",
    "/subscribe", "/register", "/paywall", "/premium",
    "accounts.google.com", "login.microsoftonline.com",
]


def _looks_like_paywall(final_url: str, domain: str) -> bool:
    """Return True if the final URL suggests a login/paywall redirect."""
    for pattern in LOGIN_REDIRECT_PATTERNS:
        if pattern in final_url.lower():
            return True
    return False


def _check_paywall_content(text: str) -> bool:
    """Check if content looks paywalled."""
    if not text or len(text) < 200:
        return True
    paywall_keywords = ["subscribe", "access denied", "subscription required",
                        "purchase access", "pay per view", "pay-per-view",
                        "subscribe to read", "this article is behind a paywall"]
    text_lower = text.lower()
    return any(kw in text_lower for kw in paywall_keywords)


def _wayback_fallback(url: str) -> Optional[str]:
    """Query Wayback Machine API for an archived copy."""
    try:
        resp = requests.get(
            "https://archive.org/wayback/available",
            params={"url": url},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        snapshots = data.get("archived_snapshots", {})
        closest = snapshots.get("closest", {})
        if closest.get("status") == "200":
            return closest.get("url")
        return None
    except Exception:
        return None


def fetch_source(url: str) -> dict:
    if not whitelist.is_allowed(url):
        raise ValueError("URL not allowed")

    domain = whitelist.get_domain(url)

    if domain in SKIP_FETCH_DOMAINS:
        return {
            "status": False,
            "error": "Google Books previews use the native viewer.",
            "fallback_url": url,
        }

    if domain in PAYWALL_DOMAINS:
        display_name = whitelist.get_display_name_for_domain(domain) or domain
        return {
            "status": False,
            "error": f"{display_name} content requires a subscription. Open in a new tab.",
            "html": "",
            "text": "",
            "title": display_name,
            "url": url,
            "domain": domain,
            "mode": "iframe",
            "fallback_url": url,
            "wayback_url": None,
        }

    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
    except requests.Timeout:
        wayback_url = _wayback_fallback(url)
        return {"status": False, "error": "Request timed out", "fallback_url": wayback_url or url, "wayback_url": wayback_url}
    except requests.RequestException:
        wayback_url = _wayback_fallback(url)
        return {"status": False, "error": "Failed to fetch source", "fallback_url": wayback_url or url, "wayback_url": wayback_url}

    if resp.status_code != 200:
        wayback_url = _wayback_fallback(url)
        if resp.status_code in (401, 403, 429):
            return {
                "status": False,
                "error": "Source blocked by the remote site. Open it directly in a new tab.",
                "fallback_url": wayback_url or url,
                "wayback_url": wayback_url,
            }
        return {"status": False, "error": "Failed to load source", "fallback_url": wayback_url or url, "wayback_url": wayback_url}

    final_domain = whitelist.get_domain(resp.url)
    if (
        final_domain != domain
        and final_domain not in PAYWALL_DOMAINS
        and _looks_like_paywall(resp.url, domain)
    ):
        wayback_url = _wayback_fallback(url)
        return {
            "status": False,
            "error": "This content requires a login or subscription. Open it directly in a new tab.",
            "fallback_url": wayback_url or url,
            "wayback_url": wayback_url,
        }

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return {"status": False, "error": "Failed to parse source content"}

    text = soup.get_text(separator=" ", strip=True)
    wayback_url = None
    if _check_paywall_content(text):
        wayback_url = _wayback_fallback(url)

    for tag in soup(["script", "form", "input", "button", "select",
                     "textarea", "iframe", "object", "embed"]):
        tag.decompose()

    if soup.head:
        base_tag = soup.new_tag("base", href=resp.url, target="_blank")
        soup.head.insert(0, base_tag)

    title = soup.title.string if soup.title else ""

    return {
        "status": True,
        "html": str(soup),
        "text": text,
        "title": title,
        "url": resp.url,
        "domain": whitelist.get_domain(resp.url),
        "mode": "iframe",
        "fallback_url": wayback_url or url,
        "wayback_url": wayback_url,
    }
