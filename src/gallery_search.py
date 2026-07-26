"""Gallery and museum collection metadata search."""

import logging

import requests

logger = logging.getLogger(__name__)

NGA_API = "https://artsearch.nga.gov.au/api"

def search_nga(query: str, limit: int = 10) -> list[dict]:
    """Search National Gallery of Australia collection."""
    try:
        resp = requests.get(
            f"{NGA_API}/search",
            params={"q": query, "limit": limit, "format": "json"},
            timeout=10,
        )
        if not resp.ok:
            return []

        data = resp.json()
        results = []
        for item in data.get("results", [])[:limit]:
            results.append({
                "source_name": "National Gallery of Australia",
                "title": item.get("title", "Untitled"),
                "artist": item.get("creator", "Unknown"),
                "year": item.get("dateCreated", ""),
                "medium": item.get("medium", ""),
                "source_url": item.get("url", ""),
                "thumbnail": item.get("thumbnail", ""),
                "snippet": item.get("description", "")[:300],
            })
        return results
    except Exception as e:
        logger.error(f"NGA search failed: {e}")
        return []


def search_ngv(query: str, limit: int = 5) -> list[dict]:
    """Search National Gallery of Victoria collection."""
    try:
        resp = requests.get(
            "https://api.ngv.vic.gov.au/api/v1/works",
            params={"q": query, "limit": limit},
            timeout=10,
        )
        if not resp.ok:
            return []

        data = resp.json()
        results = []
        for item in data[:limit] if isinstance(data, list) else data.get("data", [])[:limit]:
            results.append({
                "source_name": "National Gallery of Victoria",
                "title": item.get("title", "Untitled"),
                "artist": item.get("artist", {}).get("displayName", "Unknown"),
                "year": item.get("date", ""),
                "medium": item.get("medium", ""),
                "source_url": item.get("url", ""),
                "thumbnail": item.get("images", [{}])[0].get("url", "") if item.get("images") else "",
            })
        return results
    except Exception as e:
        logger.error(f"NGV search failed: {e}")
        return []
