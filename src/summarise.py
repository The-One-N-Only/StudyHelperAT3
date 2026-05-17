import os
import requests
import json
import logging
import src.whitelist as whitelist
import src.proxy as proxy
import src.local_ai as local_ai

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
USE_LOCAL_AI = os.getenv("USE_LOCAL_AI", "1") != "0"


def _use_local():
    return USE_LOCAL_AI or not ANTHROPIC_API_KEY


def _anthropic_request(prompt: str):
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "system": (
            "You are an academic research assistant for secondary school students. "
            "You summarise academic sources accurately and concisely. You never fabricate information. "
            "If the provided content is insufficient to answer, you must explicitly say so."
        ),
        "messages": [{"role": "user", "content": prompt}]
    }
    resp = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise ValueError("Summarisation failed")
    data = resp.json()
    return data["content"][0]["text"]


def summarise_url(url, title, atn=None, user_id=None):
    if not whitelist.is_allowed(url):
        raise ValueError("URL not allowed")

    fetched = proxy.fetch_source(url)
    if not fetched["status"]:
        return fetched

    text = fetched.get("text", "")
    if len(text) < 100:
        return {"status": False, "error": "This source does not contain sufficient information to generate a summary."}

    if _use_local():
        return local_ai.summarize_source(text, title or fetched.get("title", ""), atn)

    user_prompt = f"Title: {title}\n\nContent:\n{text[:4000]}\n\n"
    if atn:
        user_prompt += f"This summary is for the following assessment task: {atn}. Include a relevance explanation."
    user_prompt += "\n\nRespond only with JSON: {\"summary\": \"...\", \"bullets\": [\"...\"], \"relevance\": \"...\"}"

    try:
        content = _anthropic_request(user_prompt)
        result = json.loads(content)
        result["status"] = True
        logging.info(f"User {user_id} requested AI summary for {url}")
        return result
    except requests.Timeout:
        return {"status": False, "error": "Summarisation timed out"}
    except Exception:
        return {"status": False, "error": "Summarisation error"}


def summarise_file(file_id, user_id, atn=None):
    import src.db as db
    files = db.get_uploaded_files(user_id)
    file_data = next((f for f in files if f["id"] == file_id), None)
    if not file_data:
        return {"status": False, "error": "File not found"}

    text = file_data["extracted_text"]
    if len(text) < 100:
        return {"status": False, "error": "This file does not contain sufficient information to generate a summary."}

    if _use_local():
        return local_ai.summarize_source(text, file_data.get("filename", ""), atn)

    user_prompt = f"File: {file_data['filename']}\n\nContent:\n{text[:6000]}\n\n"
    if atn:
        user_prompt += f"This summary is for the following assessment task: {atn}. Include a relevance explanation."
    user_prompt += "\n\nRespond only with JSON: {\"summary\": \"...\", \"bullets\": [\"...\"], \"relevance\": \"...\"}"

    try:
        content = _anthropic_request(user_prompt)
        result = json.loads(content)
        result["status"] = True
        logging.info(f"User {user_id} requested AI summary for file {file_id}")
        return result
    except requests.Timeout:
        return {"status": False, "error": "Summarisation timed out"}
    except Exception:
        return {"status": False, "error": "Summarisation error"}
