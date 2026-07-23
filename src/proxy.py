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


def fetch_source(url):
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
        }

    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
    except requests.Timeout:
        return {"status": False, "error": "Request timed out"}
    except requests.RequestException:
        return {"status": False, "error": "Failed to fetch source"}

    if resp.status_code != 200:
        if resp.status_code in (401, 403, 429):
            return {
                "status": False,
                "error": "Source blocked by the remote site. Open it directly in a new tab.",
                "fallback_url": url,
            }
        return {"status": False, "error": "Failed to load source"}

    final_domain = whitelist.get_domain(resp.url)
    if (
        final_domain != domain
        and final_domain not in PAYWALL_DOMAINS
        and _looks_like_paywall(resp.url, domain)
    ):
        return {
            "status": False,
            "error": "This content requires a login or subscription. Open it directly in a new tab.",
            "fallback_url": url,
        }

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return {"status": False, "error": "Failed to parse source content"}

    for tag in soup(["script", "form", "input", "button", "select",
                     "textarea", "iframe", "object", "embed"]):
        tag.decompose()

    if soup.head:
        base_tag = soup.new_tag("base", href=resp.url, target="_blank")
        soup.head.insert(0, base_tag)

    title = soup.title.string if soup.title else ""

    text = soup.get_text(separator=" ", strip=True)

    return {
        "status": True,
        "html": str(soup),
        "text": text,
        "title": title,
        "url": resp.url,
        "domain": whitelist.get_domain(resp.url),
        "mode": "iframe",
    }
