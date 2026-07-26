import logging

import requests

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"

def search_papers(query: str, limit: int = 10) -> list[dict]:
    try:
        resp = requests.get(
            f"{SEMANTIC_SCHOLAR_API}/paper/search",
            params={"query": query, "limit": limit, "fields": "title,url,abstract,citationCount,publicationDate,authors,externalIds"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for paper in data.get("data", []):
            results.append({
                "source_name": "Semantic Scholar",
                "source_id": paper.get("paperId"),
                "title": paper.get("title", ""),
                "source_url": paper.get("url", ""),
                "snippet": (paper.get("abstract") or "")[:300],
                "citation_count": paper.get("citationCount", 0),
                "publication_date": paper.get("publicationDate", ""),
                "authors": [a.get("name", "") for a in paper.get("authors", [])],
                "external_ids": paper.get("externalIds", {}),
            })
        return results
    except Exception as e:
        logger.error(f"Semantic Scholar search failed: {e}")
        return []

def get_citations(paper_id: str, limit: int = 10) -> list[dict]:
    try:
        resp = requests.get(
            f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}/citations",
            params={"limit": limit, "fields": "title,url,abstract,citationCount,publicationDate,authors"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for entry in data.get("data", []):
            paper = entry.get("citingPaper", {})
            if paper.get("paperId"):
                results.append({
                    "source_name": "Semantic Scholar",
                    "source_id": paper.get("paperId"),
                    "title": paper.get("title", ""),
                    "source_url": paper.get("url", ""),
                    "snippet": (paper.get("abstract") or "")[:300],
                    "citation_count": paper.get("citationCount", 0),
                    "relation": "cited_by",
                })
        return results
    except Exception as e:
        logger.error(f"Semantic Scholar citations failed: {e}")
        return []

def get_references(paper_id: str, limit: int = 10) -> list[dict]:
    try:
        resp = requests.get(
            f"{SEMANTIC_SCHOLAR_API}/paper/{paper_id}/references",
            params={"limit": limit, "fields": "title,url,abstract,citationCount,publicationDate,authors"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for entry in data.get("data", []):
            paper = entry.get("citedPaper", {})
            if paper.get("paperId"):
                results.append({
                    "source_name": "Semantic Scholar",
                    "source_id": paper.get("paperId"),
                    "title": paper.get("title", ""),
                    "source_url": paper.get("url", ""),
                    "snippet": (paper.get("abstract") or "")[:300],
                    "citation_count": paper.get("citationCount", 0),
                    "relation": "references",
                })
        return results
    except Exception as e:
        logger.error(f"Semantic Scholar references failed: {e}")
        return []
