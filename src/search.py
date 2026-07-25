from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
from collections.abc import Mapping
from typing import Any, Optional
from urllib.parse import parse_qs, urlsplit, urlunsplit

import requests
import src.whitelist as whitelist
import src.db as db
from src.cache import cache

USER_AGENT = "StudyLib/1.0 (Academic Research Assistant)"
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")
SERP_API_KEY = os.getenv("SERP_API_KEY", "")
CUSTOM_SEARCH_PAGE_SIZE = 10
CUSTOM_SEARCH_MAX_RESULTS = 100
ITEM_THUMB_URL_MAX_LENGTH = 255

BROWSE_IMAGE_PROVIDER_SUFFIXES = (
    "serpapi.com",
    "gstatic.com",
    "googleusercontent.com",
    "books.google.com",
    "wikimedia.org",
)
GOOGLE_BOOKS_VOLUME_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,220}")

BROWSE_SOURCE_DOMAINS = {
    "wikipedia": ("en.wikipedia.org", "wikipedia"),
    "gbooks": ("books.google.com", "gbooks"),
    "britannica": ("www.britannica.com", "britannica"),
    "pubmed": ("pubmed.ncbi.nlm.nih.gov", "pubmed"),
    "natgeo": ("www.nationalgeographic.com", "natgeo"),
}

BROWSE_DEDICATED_SOURCES = {"wikipedia", "gbooks", "pubmed", "semantic_scholar", "openstax"}


class SerpApiConfigurationError(RuntimeError):
    """Raised when Browse cannot start because SerpAPI is not configured."""


class SerpApiProviderError(RuntimeError):
    """Raised when SerpAPI cannot provide a usable first result page."""


def _bounded_search_count(num_results: int, maximum: int = CUSTOM_SEARCH_MAX_RESULTS) -> int:
    try:
        requested = int(num_results)
    except (TypeError, ValueError):
        return 0
    return min(max(requested, 0), maximum)


def _browse_source_scope(source: str) -> tuple[str, Optional[str]]:
    if source in BROWSE_SOURCE_DOMAINS:
        domain, source_name = BROWSE_SOURCE_DOMAINS[source]
        return f"site:{domain}", source_name

    if source == "whitelist":
        return whitelist.get_whitelist_search_scope(), None

    if isinstance(source, str) and source.startswith("whitelist_"):
        domain = source.split("_", 1)[1]
        approved_domains = {
            *whitelist.get_whitelisted_domains(),
            *whitelist.get_whitelisted_domain_patterns(),
        }
        if domain not in approved_domains:
            return "", None
        return f"site:{domain}", whitelist.get_display_name_for_domain(domain)

    return "", None


def _browse_serp_query(query: str, scope: str, filters: dict) -> str:
    if " OR " in scope:
        scope = f"({scope})"
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


def _host_matches_suffix(hostname: str, suffix: str) -> bool:
    return hostname == suffix or hostname.endswith(f".{suffix}")


def _validate_url(value: str, max_length: int) -> Any:
    """Return a parsed urlsplit result if `value` is a safe-looking HTTPs URL;
    otherwise None.  Only applies universal safety checks — no host whitelist."""
    if not isinstance(value, str) or not value or len(value) > max_length:
        return None
    if value != value.strip() or "\\" in value or any(char.isspace() for char in value):
        return None
    try:
        parsed = urlsplit(value)
    except (TypeError, ValueError):
        return None
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.fragment
    ):
        return None
    return parsed


def _safe_browse_image_url(value: str) -> str:
    """Return a bounded HTTPS image URL from an approved host, else empty."""
    if isinstance(value, str) and value.startswith("http://"):
        value = "https://" + value[len("http://"):]
    parsed = _validate_url(value, ITEM_THUMB_URL_MAX_LENGTH)
    if parsed is None:
        return ""
    normalized = urlunsplit(("https", parsed.netloc.lower(), parsed.path, parsed.query, ""))
    if len(normalized) > ITEM_THUMB_URL_MAX_LENGTH:
        return ""
    hostname = (parsed.hostname or "").lower()
    is_provider = any(
        _host_matches_suffix(hostname, suffix)
        for suffix in BROWSE_IMAGE_PROVIDER_SUFFIXES
    )
    if not is_provider and not whitelist.is_allowed(normalized):
        return ""
    return normalized


def _safe_google_books_url(source_url: str) -> Any:
    """Return a parsed urlsplit of a safe Books URL, or None."""
    parsed = _validate_url(source_url, ITEM_THUMB_URL_MAX_LENGTH)
    if parsed is None:
        return None
    if not _host_matches_suffix((parsed.hostname or "").lower(), "books.google.com"):
        return None
    return parsed


def _google_books_volume_id(value: Any) -> str:
    """Extract a valid Google Books volume ID from a URL string or item dict.
    For dict items only trusts a raw source_id when the link proves Books origin.
    For bare strings only performs URL-parsing extraction (no raw-ID guesswork)."""
    if isinstance(value, dict):
        link = value.get("link", "")
        source_id = value.get("source_id", "")
        for candidate in (link, source_id):
            volume_id = _google_books_volume_id(candidate)
            if volume_id:
                return volume_id
        if (
            _safe_google_books_url(link) is not None
            and isinstance(source_id, str)
            and GOOGLE_BOOKS_VOLUME_ID_PATTERN.fullmatch(source_id)
        ):
            return source_id
        return ""

    if not isinstance(value, str) or not value:
        return ""

    parsed = _safe_google_books_url(value)
    if parsed is None:
        return ""

    query_ids = parse_qs(parsed.query, keep_blank_values=True).get("id", [])
    candidates = list(query_ids)
    edition_match = re.fullmatch(r"/books/edition/[^/]+/([^/]+)/?", parsed.path)
    if edition_match:
        candidates.append(edition_match.group(1))
    return next(
        (c for c in candidates if GOOGLE_BOOKS_VOLUME_ID_PATTERN.fullmatch(c)),
        "",
    )


def _google_books_cover_url(value: Any) -> str:
    """Build a Google Books cover URL from a URL string (volume-ID extraction) or item dict."""
    if isinstance(value, dict):
        volume_id = _google_books_volume_id(value)
        return _google_books_cover_url(volume_id) if volume_id else ""

    if not isinstance(value, str) or not value:
        return ""

    volume_id = _google_books_volume_id(value)
    if not volume_id:
        return ""

    return _safe_browse_image_url(
        "https://books.google.com/books/content"
        f"?id={volume_id}&printsec=frontcover&img=1&zoom=1"
    )


def _browse_result_image_url(item: dict) -> str:
    """Return the best available image URL for a search result item."""
    source_id = item.get("source_id", "")
    cover_url = (
        _google_books_cover_url(item.get("link", ""))
        or _google_books_cover_url(source_id)
    )
    if cover_url:
        return cover_url
    if (
        isinstance(source_id, str)
        and source_id
        and GOOGLE_BOOKS_VOLUME_ID_PATTERN.fullmatch(source_id)
    ):
        cover_url = _safe_browse_image_url(
            "https://books.google.com/books/content"
            f"?id={source_id}&printsec=frontcover&img=1&zoom=1"
        )
        if cover_url:
            return cover_url
    thumb = (
        _safe_browse_image_url(item.get("thumbnail", ""))
        or _safe_browse_image_url(item.get("favicon", ""))
    )
    if thumb:
        return thumb
    pagemap = item.get("pagemap", {}) or {}
    for key in ("cse_thumbnail", "cse_image", "imageobject"):
        for img in pagemap.get(key, []) or []:
            url = _safe_browse_image_url((img or {}).get("src", ""))
            if url:
                return url
    metatags = pagemap.get("metatags", []) or []
    for meta in metatags:
        og = (meta or {}).get("og:image", "")
        if og:
            url = _safe_browse_image_url(og)
            if url:
                return url
    link = item.get("link", "")
    if link:
        from urllib.parse import urlsplit
        try:
            parsed = urlsplit(link)
            favicon_url = f"https://{parsed.hostname}/favicon.ico"
            url = _safe_browse_image_url(favicon_url)
            if url:
                return url
        except Exception:
            pass
    return ""


def _make_search_cache_key(query: str, source_or_scope: str, filters_dict: dict, num_results: int) -> str:
    parts = [
        str(query).strip().lower(),
        str(source_or_scope).strip().lower(),
    ]
    if filters_dict:
        for key in sorted(filters_dict.keys()):
            val = filters_dict[key]
            if val is not None:
                parts.append(f"{key}:{str(val).strip().lower()}")
    parts.append(str(num_results))
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def browse_serpapi_search(query: str, num_results: int, source: str, filters: dict, *, user_id: int) -> list[dict]:
    """Return whitelisted SerpAPI results for one Browse source group."""
    if not SERP_API_KEY:
        raise SerpApiConfigurationError("SERP_API_KEY is not configured")

    target = _bounded_search_count(num_results)
    scope, fixed_source_name = _browse_source_scope(source)
    if target == 0 or not scope:
        return []

    # Try Redis/memory cache first
    cached_results = cache.get("search", query=query, source=source, filters=filters, num_results=target)
    if cached_results is not None:
        return cached_results

    cache_key = _make_search_cache_key(query, source, filters, target)
    cached = db.get_search_cache(cache_key)
    if cached is not None:
        item_ids = json.loads(cached["item_ids"])
        results = []
        for item_id in item_ids:
            item = db.get_item_by_id(item_id, user_id, True)
            if item:
                response_item = dict(item)
                google_books_volume_id = _google_books_volume_id({
                    "link": item["source_url"],
                    "source_id": item["source_id"],
                })
                response_item["google_books_volume_id"] = google_books_volume_id
                if google_books_volume_id:
                    response_item["accessInfo"] = {
                        "embeddable": True,
                        "webReaderLink": item["source_url"],
                        "viewability": "UNKNOWN",
                        "accessViewStatus": "NONE",
                    }
                results.append(response_item)
        return results

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
            google_books_volume_id = _google_books_volume_id(item)
            item_data = {
                "title": item.get("title", ""),
                "description": item.get("snippet", ""),
                "thumb_url": _browse_result_image_url(item),
                "thumb_mime": "image/jpeg",
                "thumb_height": 0,
                "source_url": link,
                "source_name": source_name,
                "source_id": link,
            }
            stored_item = db.get_or_create_item(item_data, user_id, True)
            response_item = dict(stored_item)
            response_item["google_books_volume_id"] = google_books_volume_id
            if google_books_volume_id:
                response_item["accessInfo"] = {
                    "embeddable": True,
                    "webReaderLink": link,
                    "viewability": "UNKNOWN",
                    "accessViewStatus": "NONE",
                }
            results.append(response_item)
            if len(results) >= target:
                break

        if len(page_items) < page_size:
            break
        start += CUSTOM_SEARCH_PAGE_SIZE

    if results:
        item_ids = json.dumps([r["id"] for r in results])
        db.set_search_cache(cache_key, item_ids)
        cache.set("search", results, ttl=300, query=query, source=source, filters=filters, num_results=target)

    return results


def normalize_identity_text(value: Any) -> str:
    """Return case-folded, collapsed whitespace for untrusted scalar input."""
    if value is None or not isinstance(value, (str, int, float, bool)):
        return ""
    return " ".join(str(value).split()).casefold()


def canonical_source_url(value: str) -> str:
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


def result_identity(item: Mapping) -> Optional[tuple]:
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


def with_response_dedupe_metadata(item: Mapping) -> dict:
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


import re
from difflib import SequenceMatcher


def _normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_title(a), _normalize_title(b)).ratio()


def _first_author_surname(item: Mapping) -> str:
    """Extract first author surname from item for grouping."""
    authors = item.get("authors") or ""
    if isinstance(authors, str) and authors:
        try:
            import json as _json
            parsed = _json.loads(authors)
            if isinstance(parsed, list) and parsed:
                first = parsed[0]
                if isinstance(first, str):
                    parts = first.replace(",", " ").split()
                    return parts[0] if parts else ""
        except Exception:
            pass
        first = authors.split(",")[0].strip()
        return first.split()[-1] if first.split() else ""
    snippet = item.get("description") or item.get("snippet") or ""
    snippet = snippet.strip()
    if snippet:
        words = snippet.split()
        return words[0] if words else ""
    return ""


def deduplicate_results(results: Any) -> list[dict]:
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

    # Second pass: fuzzy title matching grouped by first-author surname
    surname_groups: dict[str, list[int]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            continue
        surname = _first_author_surname(item)
        if surname:
            surname_groups.setdefault(surname, []).append(index)

    for surname, indices in surname_groups.items():
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                idx_i = indices[i]
                idx_j = indices[j]
                if find(idx_i) == find(idx_j):
                    continue
                title_i = _normalize_title(items[idx_i].get("title", "")) if isinstance(items[idx_i], Mapping) else ""
                title_j = _normalize_title(items[idx_j].get("title", "")) if isinstance(items[idx_j], Mapping) else ""
                if title_i and title_j and _title_similarity(title_i, title_j) > 0.85:
                    union(idx_i, idx_j)

    first_index_by_component = {}
    for index in range(len(items)):
        first_index_by_component.setdefault(find(index), index)

    deduped = []
    for index, item in enumerate(items):
        if first_index_by_component[find(index)] == index:
            deduped.append(item)

    # Add duplicate_group field to merged results
    group_map: dict[int, list[int]] = {}
    for index in range(len(items)):
        root = find(index)
        group_map.setdefault(root, []).append(index)

    seen_in_deduped = set(id(d) for d in deduped)
    for item in deduped:
        item["duplicate_group"] = []
        for idx in group_map.get(find(items.index(item)), []):
            if items[idx] is not item:
                item["duplicate_group"].append(str(idx))

    return deduped


def wikipedia(query: str, num_results: int, *, user_id: int) -> list[dict]:
    cached_results = cache.get("wikipedia", query=query, num_results=num_results)
    if cached_results is not None:
        return cached_results

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
                results.append(db.get_or_create_item(item_data, user_id, True))
        cache.set("wikipedia", results, ttl=300, query=query, num_results=num_results)
        return results
    except Exception:
        logging.exception("Wikipedia search failed")
        return []

def gbooks(query: str, num_results: int, filters: dict, *, user_id: int) -> list[dict]:
    # Try Redis/memory cache
    filter_key = tuple(sorted(filters.items())) if filters else ()
    cached_results = cache.get("gbooks", query=query, num_results=num_results, filters=filter_key)
    if cached_results is not None:
        return cached_results

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
                    "thumb_url": _safe_browse_image_url(vol.get("imageLinks", {}).get("thumbnail", "")),
                    "thumb_mime": "image/jpeg",
                    "thumb_height": 128,
                    "source_url": vol.get("infoLink", ""),
                    "source_name": "gbooks",
                    "source_id": item.get("id", "")
                }
                if item_data["source_url"] and whitelist.is_allowed(item_data["source_url"]):
                    persisted_item = db.get_or_create_item(item_data, user_id, True)
                    response_item = dict(persisted_item)
                    response_item["accessInfo"] = {
                        "embeddable": access.get("embeddable") is True,
                        "webReaderLink": access.get("webReaderLink", ""),
                        "viewability": access.get("viewability", "UNKNOWN"),
                        "accessViewStatus": access.get("accessViewStatus", "NONE"),
                    }
                    results.append(response_item)
            filter_key = tuple(sorted(filters.items())) if filters else ()
            cache.set("gbooks", results, ttl=300, query=query, num_results=num_results, filters=filter_key)
            return results
        return []
    except:
        return []


def _search_serpapi(query: str, num_results: int, scope: str, *, user_id: int) -> list[dict]:
    """Search whitelisted academic sites using SerpApi."""
    if not SERP_API_KEY or not scope:
        return []

    try:
        target = _bounded_search_count(num_results)

        # Try Redis/memory cache first
        cached_results = cache.get("search", query=query, scope=scope, num_results=target)
        if cached_results is not None:
            return cached_results

        cache_key = _make_search_cache_key(query, scope, {}, target)
        cached = db.get_search_cache(cache_key)
        if cached is not None:
            item_ids = json.loads(cached["item_ids"])
            results = []
            for item_id in item_ids:
                item = db.get_item_by_id(item_id, user_id, True)
                if item:
                    results.append(item)
            return results

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
                        "thumb_url": _browse_result_image_url(item),
                        "thumb_mime": "image/jpeg",
                        "thumb_height": 0,
                        "source_url": link,
                        "source_name": whitelist.get_display_name_for_domain(domain) if domain else "Whitelisted Source",
                        "source_id": link
                    }
                    page_results.append(
                        db.get_or_create_item(item_data, user_id, True)
                    )
                    if len(results) + len(page_results) >= target:
                        break
            except Exception:
                break
            results.extend(page_results)

            if len(page_items) < page_size:
                break
            start += page_size
        if results:
            item_ids = json.dumps([r["id"] for r in results])
            db.set_search_cache(cache_key, item_ids)
            cache.set("search", results, ttl=300, query=query, scope=scope, num_results=target)
        return results
    except Exception:
        logging.exception("_search_serpapi failed for scope %s", scope)
        return []


def get_related_sources(item_id: int, user_id: int, limit: int = 5) -> list[dict]:
    """Find items saved by users who also saved the given item, excluding the current user's own items."""
    try:
        import src.db as db_mod
        with db_mod.SessionLocal() as session:
            subq = (
                session.query(db_mod.UserToSaved.user_id)
                .filter(db_mod.UserToSaved.item_id == item_id)
                .filter(db_mod.UserToSaved.user_id != user_id)
                .subquery()
            )
            related = (
                session.query(db_mod.Item)
                .join(db_mod.UserToSaved, db_mod.UserToSaved.item_id == db_mod.Item.id)
                .filter(db_mod.UserToSaved.user_id.in_(subq))
                .filter(db_mod.UserToSaved.item_id != item_id)
                .filter(db_mod.UserToSaved.user_id != user_id)
                .group_by(db_mod.Item.id)
                .order_by(db_mod.func.count(db_mod.Item.id).desc())
                .limit(limit)
                .all()
            )
            return [db_mod._item_to_dict(item) for item in related]
    except Exception:
        logging.exception("Failed to get related sources")
        return []


def semantic_scholar(query: str, num_results: int, *, user_id: int) -> list[dict]:
    import src.semantic_scholar as ss
    try:
        papers = ss.search_papers(query, limit=num_results)
        results = []
        for paper in papers:
            item_data = {
                "title": paper.get("title", ""),
                "description": paper.get("snippet", ""),
                "thumb_url": "",
                "thumb_mime": "image/jpeg",
                "thumb_height": 0,
                "source_url": paper.get("source_url", f"https://api.semanticscholar.org/CorpusID:{paper.get('source_id', '')}"),
                "source_name": "semantic_scholar",
                "source_id": paper.get("source_id", ""),
            }
            persisted = db.get_or_create_item(item_data, user_id, True)
            persisted["citation_count"] = paper.get("citation_count", 0)
            persisted["publication_date"] = paper.get("publication_date", "")
            persisted["authors"] = paper.get("authors", [])
            results.append(persisted)
        return results
    except Exception:
        logging.exception("Semantic Scholar search failed")
        return []


def oer_search(query: str, num_results: int, *, user_id: int) -> list[dict]:
    import src.oer as oer
    try:
        books = oer.search_openstax(query, limit=num_results)
        results = []
        for book in books:
            item_data = {
                "title": book.get("title", ""),
                "description": book.get("snippet", ""),
                "thumb_url": "",
                "thumb_mime": "image/jpeg",
                "thumb_height": 0,
                "source_url": book.get("source_url", ""),
                "source_name": "openstax",
                "source_id": book.get("source_url", ""),
            }
            persisted = db.get_or_create_item(item_data, user_id, True)
            results.append(persisted)
        return results
    except Exception:
        logging.exception("OpenStax search failed")
        return []


def whitelist_search(query: str, num_results: int, domains: Optional[list[str]] = None, *, user_id: int) -> list[dict]:
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
