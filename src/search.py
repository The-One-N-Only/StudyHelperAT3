import os
import re
from collections.abc import Mapping
from urllib.parse import urlsplit, urlunsplit

import requests
import src.whitelist as whitelist
import src.db as db
import src.pubmed as pubmed

USER_AGENT = "StudyLib/1.0 (Academic Research Assistant)"
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
SERP_API_KEY = os.getenv("SERP_API_KEY", "")


def normalize_identity_text(value):
    """Return case-folded, collapsed whitespace for untrusted scalar input."""
    if value is None or not isinstance(value, (str, int, float, bool)):
        return ""
    return " ".join(str(value).split()).casefold()


def canonical_source_url(value):
    """Return normalized absolute HTTP(S) URL without fragment, or empty string."""
    if not isinstance(value, str):
        return ""

    raw_value = value.strip()
    if not raw_value or any(character.isspace() for character in raw_value):
        return ""

    try:
        parsed = urlsplit(raw_value)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        port = parsed.port
    except (TypeError, ValueError):
        return ""

    if scheme not in {"http", "https"} or not parsed.netloc or not hostname:
        return ""

    normalized_hostname = hostname.lower()
    if ":" in normalized_hostname:
        normalized_hostname = f"[{normalized_hostname}]"

    userinfo = ""
    if parsed.username is not None:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo += f":{parsed.password}"
        userinfo += "@"

    netloc = f"{userinfo}{normalized_hostname}"
    if port is not None:
        netloc += f":{port}"

    return urlunsplit((scheme, netloc, parsed.path, parsed.query, ""))


def result_identity(item):
    """Return source/id, URL, display tuple, or None in approved priority order."""
    if not isinstance(item, Mapping):
        return None

    source_name = normalize_identity_text(item.get("source_name"))
    source_id_value = item.get("source_id")
    if isinstance(source_id_value, (str, int, float, bool)):
        source_id = str(source_id_value).strip()
    else:
        source_id = ""

    if source_name and source_id:
        return ("source_id", source_name, source_id)

    source_url = canonical_source_url(item.get("source_url"))
    if source_url:
        return ("url", source_url)

    title = normalize_identity_text(item.get("title"))
    if source_name and title:
        return ("display", source_name, title)

    return None


def deduplicate_results(results):
    """Preserve first-seen order; reject repeated primary identity OR canonical URL."""
    if results is None or isinstance(results, (str, bytes, Mapping)):
        return []

    try:
        result_items = iter(results)
    except TypeError:
        return []

    unique_results = []
    seen_identities = set()
    seen_urls = set()
    for item in result_items:
        identity = result_identity(item)
        source_url = (
            canonical_source_url(item.get("source_url"))
            if isinstance(item, Mapping)
            else ""
        )

        if identity is not None and identity in seen_identities:
            continue
        if source_url and source_url in seen_urls:
            continue

        unique_results.append(item)
        if identity is not None:
            seen_identities.add(identity)
        if source_url:
            seen_urls.add(source_url)

    return unique_results


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
    """Search whitelisted academic sites using SerpApi."""
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


def _search_whitelist_site(query, num_results, domain, *, user_id):
    """Search a specific whitelisted domain and return up to `num_results` items."""
    if not domain:
        return []

    scope = f"site:{domain}"
    if SERP_API_KEY:
        return _search_serpapi(query, min(num_results, 10), scope, user_id=user_id)

    display_name = whitelist.get_display_name_for_domain(domain)
    if GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
        try:
            q = f"{query} {scope}"
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": GOOGLE_SEARCH_API_KEY,
                "cx": GOOGLE_SEARCH_ENGINE_ID,
                "q": q,
                "num": min(num_results, 10)
            }
            headers = {"User-Agent": USER_AGENT}
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for item in data.get("items", []):
                link = item.get("link", "")
                if not link or not whitelist.is_allowed(link):
                    continue

                item_data = {
                    "title": item.get("title", "").replace("<b>", "").replace("</b>", "").replace("&#39;", "'"),
                    "description": item.get("snippet", "").replace("<b>", "").replace("</b>", "").replace("&#39;", "'"),
                    "thumb_url": "",
                    "thumb_mime": "image/jpeg",
                    "thumb_height": 0,
                    "source_url": link,
                    "source_name": display_name,
                    "source_id": link
                }
                results.append(db.get_item_by_source(item_data["source_name"], item_data["source_id"], user_id, True) or db.create_item(item_data, user_id, True))
            return results
        except Exception:
            return []

    # Fallback search implementations for popular whitelisted domains.
    if domain == 'en.wikipedia.org':
        return wikipedia(query, min(num_results, 1), user_id=user_id)
    if domain == 'pubmed.ncbi.nlm.nih.gov':
        return pubmed.search(query, min(num_results, 1), mesh_terms=None, min_date=None, max_date=None, user_id=user_id)
    if domain == 'books.google.com':
        return gbooks(query, min(num_results, 1), {}, user_id=user_id)
    if domain == 'scholar.google.com':
        return google_scholar(query, min(num_results, 1), user_id=user_id)

    return []


def whitelist_search(query, num_results, domains=None, *, user_id):
    """Search across approved whitelisted academic domains using Google Custom Search or SerpApi."""
    explicit_domains = domains
    if explicit_domains is None:
        explicit_domains = whitelist.get_whitelisted_domains()

    if not explicit_domains:
        return []

    if SERP_API_KEY and domains is None:
        scope = whitelist.get_whitelist_search_scope()
        return _search_serpapi(query, min(num_results, 10), scope, user_id=user_id)

    # Ensure each domain contributes at most one result to avoid overwhelming the UI.
    results = []
    for domain in explicit_domains:
        site_results = _search_whitelist_site(query, min(num_results, 1), domain, user_id=user_id)
        if site_results:
            results.extend(site_results[:1])

    return results
