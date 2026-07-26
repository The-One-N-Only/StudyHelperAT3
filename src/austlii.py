"""AustLII search for Australian case law and legislation."""

import logging

import requests

logger = logging.getLogger(__name__)

AUSTLII_SEARCH_URL = "https://www.austlii.edu.au/cgi-bin/"

def search_cases(query: str, limit: int = 10) -> list[dict]:
    """Search Australian case law via AustLII."""
    try:
        resp = requests.get(
            "https://www.austlii.edu.au/cgi-bin/sinosrch.cgi",
            params={
                "query": query,
                "method": "all",
                "results": limit,
                "submit": "Search",
                "mask_path": "",
                "mask_app": "",
                "mask_wb": "",
                "mask_ph": "",
                "mask_pl": "",
                "mask_lt": "",
                "mask_pn": "",
                "mask_pc": "",
                "mask_pi": "",
                "mask_pm": "",
            },
            timeout=15,
        )
        resp.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for item in soup.select("li, .result-item")[:limit]:
            link = item.find("a") if item.find("a") else None
            if link and link.get("href"):
                results.append({
                    "source_name": "AustLII",
                    "title": link.get_text(strip=True) or query,
                    "source_url": link["href"] if link["href"].startswith("http") else f"https://www.austlii.edu.au{link['href']}",
                    "snippet": item.get_text(strip=True)[:300],
                    "content_type": "legal_case",
                })

        return results if results else _fallback_search(query, limit)
    except Exception as e:
        logger.error(f"AustLII search failed: {e}")
        return _fallback_search(query, limit)


def _fallback_search(query: str, _limit: int) -> list[dict]:
    """Fallback: return AustLII search URL for manual browsing."""
    return [{
        "source_name": "AustLII",
        "title": f"Search AustLII for: {query}",
        "source_url": f"https://www.austlii.edu.au/cgi-bin/sinosrch.cgi?query={query}&method=all",
        "snippet": "View results directly on AustLII. Use their advanced search for precise legal research.",
        "content_type": "legal_case",
    }]
