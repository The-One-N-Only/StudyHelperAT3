"""AIATSIS catalogue search with cultural protocol awareness."""

import logging

import requests

logger = logging.getLogger(__name__)

AIATSIS_CATALOGUE = "https://aiatsis.gov.au/api/catalogue"

CULTURAL_SENSITIVITY_NOTICE = (
    "Aboriginal and Torres Strait Islander peoples should be aware that "
    "this catalogue may contain images, voices or names of deceased persons, "
    "or content that may be culturally sensitive."
)

PROTOCOL_NOTES = {
    "restricted": "This item requires community consultation before access.",
    "men_only": "This item is restricted to Aboriginal and Torres Strait Islander men.",
    "women_only": "This item is restricted to Aboriginal and Torres Strait Islander women.",
    "secret_sacred": "This item contains secret/sacred material and access is restricted.",
}

def search_catalogue(query: str, limit: int = 10) -> list[dict]:
    """Search AIATSIS public catalogue."""
    try:
        resp = requests.get(
            AIATSIS_CATALOGUE,
            params={"q": query, "limit": limit},
            timeout=15,
        )
        if not resp.ok:
            return []

        data = resp.json()
        results = []
        for item in data.get("results", [])[:limit]:
            access_notice = item.get("accessConditions", "open")
            protocol = PROTOCOL_NOTES.get(access_notice, "")

            results.append({
                "source_name": "AIATSIS",
                "title": item.get("title", "Untitled"),
                "source_url": item.get("url", ""),
                "snippet": item.get("description", "")[:300],
                "access": access_notice,
                "cultural_sensitivity": CULTURAL_SENSITIVITY_NOTICE,
                "protocol_note": protocol,
            })
        return results
    except Exception as e:
        logger.error(f"AIATSIS search failed: {e}")
        return []
