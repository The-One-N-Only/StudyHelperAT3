import requests
from bs4 import BeautifulSoup

import src.whitelist as whitelist


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
        resp = requests.get(url, timeout=10)
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
