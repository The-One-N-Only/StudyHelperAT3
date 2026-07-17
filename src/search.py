import os
import re
import requests
from urllib.parse import quote
import json
import xml.etree.ElementTree as ET
import src.whitelist as whitelist
import src.db as db
from dotenv import load_dotenv

load_dotenv()

USER_AGENT = "StudyLib/1.0 (Academic Research Assistant)"
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
SERP_API_KEY = os.getenv("SERP_API_KEY", "")


def wikipedia(query, num_results, *, user_id):
    search_url = "https://en.wikipedia.org/w/api.php"
    headers = {"User-Agent": USER_AGENT}
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": num_results,
        "srprop": "snippet",
        "format": "json"
    }
    try:
        resp = requests.get(search_url, params=params, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []

        search_data = resp.json()
        search_results = search_data.get("query", {}).get("search", [])
        if not search_results:
            return []

        page_ids = "|".join(str(item.get("pageid")) for item in search_results if item.get("pageid"))
        page_info = {}
        if page_ids:
            info_params = {
                "action": "query",
                "pageids": page_ids,
                "prop": "info|pageimages",
                "inprop": "url",
                "pithumbsize": 200,
                "format": "json"
            }
            info_resp = requests.get(search_url, params=info_params, headers=headers, timeout=10)
            if info_resp.status_code == 200:
                page_info = info_resp.json().get("query", {}).get("pages", {})

        results = []
        for item in search_results:
            pageid = str(item.get("pageid", ""))
            page = page_info.get(pageid, {})
            source_url = page.get("fullurl") or f"https://en.wikipedia.org/?curid={pageid}"
            description = re.sub(r"<[^>]+>", "", item.get("snippet", "")).strip()
            item_data = {
                "title": item.get("title", ""),
                "description": description,
                "thumb_url": page.get("thumbnail", {}).get("source", ""),
                "thumb_mime": page.get("thumbnail", {}).get("mime", "image/jpeg"),
                "thumb_height": page.get("thumbnail", {}).get("height", 100),
                "source_url": source_url,
                "source_name": "wikipedia",
                "source_id": pageid
            }
            if item_data["source_url"] and whitelist.is_allowed(item_data["source_url"]):
                results.append(db.get_item_by_source("wikipedia", item_data["source_id"], user_id, True) or db.create_item(item_data, user_id, True))
        return results
    except Exception:
        return []

def gbooks(query, num_results, filters, *, user_id):
    params = {
        "q": query,
        "maxResults": num_results
    }
    if GOOGLE_BOOKS_API_KEY:
        params["key"] = GOOGLE_BOOKS_API_KEY
    if filters.get("download") == "epub":
        params["download"] = "epub"
    if filters.get("available") in ["partial", "free-ebooks", "full"]:
        params["filter"] = filters["available"]
    if filters.get("print") in ["all", "books", "magazines"]:
        params["printType"] = filters["print"]

    url = "https://www.googleapis.com/books/v1/volumes"
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for item in data.get("items", []):
                vol = item.get("volumeInfo", {})
                item_data = {
                    "title": vol.get("title", ""),
                    "description": vol.get("description", ""),
                    "thumb_url": vol.get("imageLinks", {}).get("thumbnail", ""),
                    "thumb_mime": "image/jpeg",
                    "thumb_height": 128,
                    "source_url": vol.get("infoLink", ""),
                    "source_name": "gbooks",
                    "source_id": item.get("id", "")
                }
                if item_data["source_url"] and whitelist.is_allowed(item_data["source_url"]):
                    results.append(db.get_item_by_source("gbooks", item_data["source_id"], user_id, True) or db.create_item(item_data, user_id, True))
            return results
        return []
    except:
        return []


def _search_serpapi(query, num_results, scope, *, user_id):
    """Search one whitelisted academic site using SerpApi."""
    if not SERP_API_KEY or not scope:
        return []

    try:
        q = f"{query} ({scope})".strip()
        params = {
            "q": q,
            "num": min(num_results, 10),
            "api_key": SERP_API_KEY,
            "engine": "google"
        }
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(
            "https://serpapi.com/search",
            params=params,
            headers=headers,
            timeout=10
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        results = []
        for item in data.get("organic_results", []):
            link = item.get("link", "")
            if not link or not whitelist.is_allowed(link):
                continue

            domain = whitelist.get_domain(link)
            item_data = {
                "title": item.get("title", ""),
                "description": item.get("snippet", ""),
                "thumb_url": "",
                "thumb_mime": "image/jpeg",
                "thumb_height": 0,
                "source_url": link,
                "source_name": whitelist.get_display_name_for_domain(domain) if domain else "Whitelisted Source",
                "source_id": link
            }
            results.append(
                db.get_item_by_source(
                    item_data["source_name"], item_data["source_id"], user_id, True
                ) or db.create_item(item_data, user_id, True)
            )
        return results
    except Exception:
        return []


def _search_whitelist_site(query, num_results, domain, *, user_id):
    """Search one whitelisted domain via SerpAPI and return up to ten results."""
    if not query or not domain:
        return []

    scope = f"site:{domain}"
    domain_results = _search_serpapi(query, num_results, scope, user_id=user_id)
    if domain_results:
        return domain_results

    fallback_link = f"https://{domain}/"
    if whitelist.is_allowed(fallback_link):
        item_data = {
            "title": f"{domain} homepage",
            "description": f"Search results for '{query}' were not available from the API.",
            "thumb_url": "",
            "thumb_mime": "image/jpeg",
            "thumb_height": 0,
            "source_url": fallback_link,
            "source_name": whitelist.get_display_name_for_domain(domain) if domain else "Whitelisted Source",
            "source_id": fallback_link,
        }
        return [
            db.get_item_by_source(item_data["source_name"], item_data["source_id"], user_id, True)
            or db.create_item(item_data, user_id, True)
        ]
    return []


def whitelist_search(query, num_results, domains=None, *, user_id):
    """Search each whitelisted domain and return up to ten results per domain."""
    if not query:
        return []

    requested_domains = domains or whitelist.get_whitelisted_domains()
    if not requested_domains:
        return []

    results = []
    for domain in requested_domains:
        domain_items = _search_whitelist_site(query, num_results, domain, user_id=user_id) or []
        # assign per-domain rank (1..n) so the UI can reveal them incrementally
        for i, it in enumerate(domain_items[:10], start=1):
            try:
                it['whitelist_rank'] = int(it.get('whitelist_rank', i))
            except Exception:
                it['whitelist_rank'] = i
        results.extend(domain_items)
    return results


def google_scholar(query, num_results, *, user_id):
    """
    Search Google Scholar for academic papers.
    Note: This is a simplified implementation. Google Scholar doesn't have a public API,
    so this would need to be implemented using scraping or Google Custom Search API.
    """
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        return []
    
    try:
        # Use Google Custom Search API configured to search scholar.google.com
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_SEARCH_API_KEY,
            "cx": GOOGLE_SEARCH_ENGINE_ID,  # Custom search engine ID configured for academic sites
            "q": query,
            "num": min(num_results, 10)  # API limit is 10 per request
        }
        
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        results = []
        
        for item in data.get("items", []):
            # Only include results from whitelisted domains
            link = item.get("link", "")
            if not whitelist.is_allowed(link):
                continue
                
            item_data = {
                "title": item.get("title", "").replace("<b>", "").replace("</b>", "").replace("&#39;", "'"),
                "description": item.get("snippet", "").replace("<b>", "").replace("</b>", "").replace("&#39;", "'"),
                "thumb_url": "",
                "thumb_mime": "image/jpeg",
                "thumb_height": 0,
                "source_url": link,
                "source_name": whitelist.get_display_name_for_domain('scholar.google.com'),
                "source_id": link  # Use URL as ID since no unique ID from search
            }
            
            results.append(db.get_item_by_source(item_data["source_name"], item_data["source_id"], user_id, True) or db.create_item(item_data, user_id, True))
            
        return results
    except:
        return []


def _normalize_search_result(link, title, description):
    normalized_link = (link or "").strip()
    if not normalized_link:
        return None
    if not whitelist.is_allowed(normalized_link):
        return None
    return {
        "title": (title or "").replace("<b>", "").replace("</b>", "").replace("&#39;", "'"),
        "description": (description or "").replace("<b>", "").replace("</b>", "").replace("&#39;", "'"),
        "thumb_url": "",
        "thumb_mime": "image/jpeg",
        "thumb_height": 0,
        "source_url": normalized_link,
        "source_name": "whitelist",
        "source_id": normalized_link,
    }


def _search_with_google_cse(query, num_results):
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        return []

    scopes = whitelist.get_whitelist_search_scope()
    if not scopes:
        return []

    results = []
    seen_links = set()
    per_domain_limit = max(1, min(num_results, 10))

    for scope in scopes:
        if len(results) >= num_results:
            break

        q = f"{query} {scope}"
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": GOOGLE_SEARCH_API_KEY,
                "cx": GOOGLE_SEARCH_ENGINE_ID,
                "q": q,
                "num": per_domain_limit
            }

            headers = {"User-Agent": USER_AGENT}
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue

            data = resp.json()
            for item in data.get("items", []):
                link = item.get("link", "")
                if not whitelist.is_allowed(link) or link in seen_links:
                    continue

                seen_links.add(link)
                item_data = {
                    "title": item.get("title", "").replace("<b>", "").replace("</b>", "").replace("&#39;", "'"),
                    "description": item.get("snippet", "").replace("<b>", "").replace("</b>", "").replace("&#39;", "'"),
                    "thumb_url": "",
                    "thumb_mime": "image/jpeg",
                    "thumb_height": 0,
                    "source_url": link,
                    "source_name": "whitelist",
                    "source_id": link
                }
                results.append(db.get_item_by_source("whitelist", item_data["source_id"], user_id, True) or db.create_item(item_data, user_id, True))
                if len(results) >= num_results:
                    break
        except Exception:
            continue

    return results


def _search_with_bing_rss(query, num_results):
    """Fallback stub used by tests: attempt to fetch RSS/ATOM feeds for each scope.
    The implementation here is minimal and returns an empty list by default.
    """
    return []