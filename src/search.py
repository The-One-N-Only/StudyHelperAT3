import json
import logging
import math
import os
import re
from collections.abc import Mapping
from urllib.parse import urlsplit, urlunsplit

import requests
import src.whitelist as whitelist
import src.db as db

USER_AGENT = "StudyLib/1.0 (Academic Research Assistant)"
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")
SERP_API_KEY = os.getenv("SERP_API_KEY", "")
CUSTOM_SEARCH_PAGE_SIZE = 10
CUSTOM_SEARCH_MAX_RESULTS = 100

BROWSE_SOURCE_DOMAINS = {
    "wikipedia": ("en.wikipedia.org", "wikipedia"),
    "gbooks": ("books.google.com", "gbooks"),
    "scholar": ("scholar.google.com", "scholar"),
    "pubmed": ("pubmed.ncbi.nlm.nih.gov", "pubmed"),
}


class SerpApiConfigurationError(RuntimeError):
    """Raised when Browse cannot start because SerpAPI is not configured."""


class SerpApiProviderError(RuntimeError):
    """Raised when SerpAPI cannot provide a usable first result page."""


def _bounded_search_count(num_results, maximum=CUSTOM_SEARCH_MAX_RESULTS):
    try:
        requested = int(num_results)
    except (TypeError, ValueError):
        return 0
    return min(max(requested, 0), maximum)


def _browse_source_scope(source):
    if source in BROWSE_SOURCE_DOMAINS:
        domain, source_name = BROWSE_SOURCE_DOMAINS[source]
        return f"site:{domain}", source_name

    if source == "whitelist":
        return whitelist.get_whitelist_search_scope(), None

    if isinstance(source, str) and source.startswith("whitelist_"):
        domain = source.split("_", 1)[1]
        if domain not in whitelist.get_whitelisted_domains():
            return "", None
        return f"site:{domain}", whitelist.get_display_name_for_domain(domain)

    return "", None


def _browse_serp_query(query, scope, filters):
    terms = [str(query).strip(), scope]
    filters = filters if isinstance(filters, Mapping) else {}

    min_date = str(filters.get("min_date", "")).strip()
    max_date = str(filters.get("max_date", "")).strip()
    if min_date.isdigit():
        terms.append(f"after:{int(min_date) - 1}-12-31")
    if max_date.isdigit():
        terms.append(f"before:{int(max_date) + 1}-01-01")

    content_type = str(filters.get("content_type", "")).strip()
    if content_type in {"review", "survey", "case study", "full text"}:
        terms.append(f'"{content_type}"')

    return " ".join(term for term in terms if term)


def browse_serpapi_search(query, num_results, source, filters, *, user_id):
    """Return whitelisted SerpAPI results for one Browse source group."""
    if not SERP_API_KEY:
        raise SerpApiConfigurationError("SERP_API_KEY is not configured")

    target = _bounded_search_count(num_results)
    scope, fixed_source_name = _browse_source_scope(source)
    if target == 0 or not scope:
        return []

    scoped_query = _browse_serp_query(query, scope, filters)
    results = []
    start = 0
    while len(results) < target and start < CUSTOM_SEARCH_MAX_RESULTS:
        page_size = min(CUSTOM_SEARCH_PAGE_SIZE, target - len(results))
        params = {
            "q": scoped_query,
            "num": page_size,
            "start": start,
            "api_key": SERP_API_KEY,
            "engine": "google",
        }
        try:
            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=10,
            )
            payload = response.json()
            if response.status_code != 200:
                raise ValueError(f"SerpAPI returned HTTP {response.status_code}")
            if not isinstance(payload, Mapping):
                raise ValueError("SerpAPI returned a non-object response")
            if payload.get("error"):
                raise ValueError(str(payload["error"]))
            page_items = payload.get("organic_results", [])
            if not isinstance(page_items, list) or not all(
                isinstance(item, Mapping) for item in page_items
            ):
                raise ValueError("SerpAPI returned invalid organic results")
        except Exception as error:
            logging.exception(
                "SerpAPI Browse search failed for source %s at offset %s",
                source,
                start,
            )
            if results:
                break
            raise SerpApiProviderError("SerpAPI Browse search failed") from error

        if not page_items:
            break

        for item in page_items[:page_size]:
            link = item.get("link", "")
            if not link or not whitelist.is_allowed(link):
                continue
            domain = whitelist.get_domain(link)
            source_name = fixed_source_name or (
                whitelist.get_display_name_for_domain(domain)
                if domain
                else "Whitelisted Source"
            )
            item_data = {
                "title": item.get("title", ""),
                "description": item.get("snippet", ""),
                "thumb_url": item.get("thumbnail", ""),
                "thumb_mime": "image/jpeg",
                "thumb_height": 0,
                "source_url": link,
                "source_name": source_name,
                "source_id": link,
            }
            results.append(
                db.get_item_by_source(
                    item_data["source_name"],
                    item_data["source_id"],
                    user_id,
                    True,
                )
                or db.create_item(item_data, user_id, True)
            )
            if len(results) >= target:
                break

        if len(page_items) < page_size:
            break
        start += CUSTOM_SEARCH_PAGE_SIZE

    return results


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
    if (
        not raw_value
        or "\\" in raw_value
        or any(character.isspace() for character in raw_value)
    ):
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
    if isinstance(source_id_value, str):
        source_id = str(source_id_value).strip()
    elif isinstance(source_id_value, bool):
        source_id = "true" if source_id_value else "false"
    elif isinstance(source_id_value, int):
        source_id = str(source_id_value)
    elif isinstance(source_id_value, float) and math.isfinite(source_id_value):
        source_id = (
            str(int(source_id_value))
            if source_id_value.is_integer()
            else str(source_id_value)
        )
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


def with_response_dedupe_metadata(item):
    """Return a result copy carrying the server's canonical dedupe keys."""
    if not isinstance(item, Mapping):
        return item

    response_item = dict(item)
    identity = result_identity(item)
    response_item["_dedupe_identity"] = (
        json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
        if identity is not None
        else ""
    )
    response_item["_canonical_source_url"] = canonical_source_url(
        item.get("source_url")
    )
    return response_item


def deduplicate_results(results):
    """Keep first item from each identity/URL connected component, in order."""
    if results is None or isinstance(results, (str, bytes, Mapping)):
        return []

    try:
        result_items = iter(results)
    except TypeError:
        return []

    items = list(result_items)
    parents = list(range(len(items)))
    ranks = [0] * len(items)

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left, right):
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if ranks[left_root] < ranks[right_root]:
            left_root, right_root = right_root, left_root
        parents[right_root] = left_root
        if ranks[left_root] == ranks[right_root]:
            ranks[left_root] += 1

    first_index_by_key = {}
    for index, item in enumerate(items):
        identity = result_identity(item)
        source_url = (
            canonical_source_url(item.get("source_url"))
            if isinstance(item, Mapping)
            else ""
        )
        keys = []
        if identity is not None:
            keys.append(("identity", identity))
        if source_url:
            keys.append(("url", source_url))

        for key in keys:
            previous_index = first_index_by_key.get(key)
            if previous_index is None:
                first_index_by_key[key] = index
            else:
                union(index, previous_index)

    first_index_by_component = {}
    for index in range(len(items)):
        first_index_by_component.setdefault(find(index), index)

    return [
        item
        for index, item in enumerate(items)
        if first_index_by_component[find(index)] == index
    ]


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
        "maxResults": min(max(int(num_results), 0), 40)
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
                access = item.get("accessInfo", {})
                if not isinstance(access, Mapping):
                    access = {}
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
                    persisted_item = (
                        db.get_item_by_source(
                            "gbooks", item_data["source_id"], user_id, True
                        )
                        or db.create_item(item_data, user_id, True)
                    )
                    response_item = dict(persisted_item)
                    response_item["accessInfo"] = {
                        "embeddable": access.get("embeddable") is True,
                        "webReaderLink": access.get("webReaderLink", ""),
                        "viewability": access.get("viewability", "UNKNOWN"),
                        "accessViewStatus": access.get("accessViewStatus", "NONE"),
                    }
                    results.append(response_item)
            return results
        return []
    except:
        return []


def _search_serpapi(query, num_results, scope, *, user_id):
    """Search whitelisted academic sites using SerpApi."""
    if not SERP_API_KEY or not scope:
        return []

    try:
        target = _bounded_search_count(num_results)
        q = f"{query} ({scope})".strip()
        results = []
        start = 0
        while len(results) < target and start < CUSTOM_SEARCH_MAX_RESULTS:
            page_size = min(
                CUSTOM_SEARCH_PAGE_SIZE,
                target - len(results),
                CUSTOM_SEARCH_MAX_RESULTS - start,
            )
            params = {
                "q": q,
                "num": page_size,
                "start": start,
                "api_key": SERP_API_KEY,
                "engine": "google"
            }
            headers = {"User-Agent": USER_AGENT}
            try:
                resp = requests.get(
                    "https://serpapi.com/search",
                    params=params,
                    headers=headers,
                    timeout=10
                )
                if resp.status_code != 200:
                    break
                payload = resp.json()
                if not isinstance(payload, Mapping):
                    break
                page_items = payload.get("organic_results", [])
            except Exception:
                # Later-page provider corruption must not erase earlier good pages.
                break
            if not isinstance(page_items, list) or not page_items:
                break
            page_items = page_items[:page_size]
            page_results = []
            try:
                for item in page_items:
                    if not isinstance(item, Mapping):
                        raise ValueError("Malformed SerpApi result item")
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
                    page_results.append(
                        db.get_item_by_source(
                            item_data["source_name"], item_data["source_id"], user_id, True
                        ) or db.create_item(item_data, user_id, True)
                    )
                    if len(results) + len(page_results) >= target:
                        break
            except Exception:
                break
            results.extend(page_results)

            if len(page_items) < page_size:
                break
            start += page_size
        return results
    except Exception:
        return []


def whitelist_search(query, num_results, domains=None, *, user_id):
    """Search approved academic domains through SerpAPI only."""
    if not SERP_API_KEY:
        raise SerpApiConfigurationError("SERP_API_KEY is not configured")

    target = _bounded_search_count(num_results)
    if target == 0:
        return []

    if domains is None:
        scope = whitelist.get_whitelist_search_scope()
        return _search_serpapi(query, target, scope, user_id=user_id)

    results = []
    approved_domains = set(whitelist.get_whitelisted_domains())
    for domain in domains:
        if domain not in approved_domains:
            continue
        remaining = target - len(results)
        if remaining <= 0:
            break
        results.extend(
            _search_serpapi(
                query,
                remaining,
                f"site:{domain}",
                user_id=user_id,
            )[:remaining]
        )

    return results
