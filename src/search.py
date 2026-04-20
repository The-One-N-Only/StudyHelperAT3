import requests
from urllib.parse import quote
import json
import src.whitelist as whitelist
import src.db as db

USER_AGENT = "StudyLib/1.0 (Academic Research Assistant)"

def wikipedia(query, num_results, *, user_id):
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(query)}"
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            item_data = {
                "title": data.get("title", ""),
                "description": data.get("extract", ""),
                "thumb_url": data.get("thumbnail", {}).get("source", ""),
                "thumb_mime": data.get("thumbnail", {}).get("mime", "image/jpeg"),
                "thumb_height": data.get("thumbnail", {}).get("height", 100),
                "source_url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "source_name": "wikipedia",
                "source_id": str(data.get("pageid", ""))
            }
            if item_data["source_url"] and whitelist.is_allowed(item_data["source_url"]):
                return [db.get_item_by_source("wikipedia", item_data["source_id"], user_id, True) or db.create_item(item_data, user_id, True)]
        return []
    except:
        return []

def gbooks(query, num_results, filters, *, user_id):
    params = {
        "q": query,
        "maxResults": num_results,
        "key": ""  # No key needed for basic search
    }
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