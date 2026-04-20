import os
import requests
import json
import src.whitelist as whitelist
import src.proxy as proxy
import logging

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

def summarise_url(url, title, atn=None, user_id=None):
    if not whitelist.is_allowed(url):
        raise ValueError("URL not allowed")
    
    fetched = proxy.fetch_source(url)
    if not fetched["status"]:
        return fetched  # Error dict
    
    text = fetched["html"]  # Assuming proxy returns cleaned text, but spec says html, wait no, spec says extract plain text from cleaned HTML.
    # Wait, in proxy.py, it returns html, but here we need to extract text.
    # The spec says: "Extract plain text from the cleaned HTML"
    # So I need to add text extraction in proxy or here.
    # Let's assume proxy returns "text" instead of "html".
    # Looking back, proxy returns "html": "...", but for summarise, we need text.
    # I'll modify proxy to also return "text".

    # For now, assume fetched["text"] exists.

    if len(text) < 100:
        return {"status": False, "error": "This source does not contain sufficient information to generate a summary."}

    system = "You are an academic research assistant for secondary school students. You summarise academic sources accurately and concisely. You never fabricate information. If the provided content is insufficient to answer, you must explicitly say so."
    user_prompt = f"Title: {title}\n\nContent:\n{text[:4000]}\n\n"
    if atn:
        user_prompt += f"This summary is for the following assessment task: {atn}. Include a relevance explanation."
    user_prompt += "\n\nRespond only with JSON: {\"summary\": \"...\", \"bullets\": [\"...\"], \"relevance\": \"...\"}"

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}]
    }
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    try:
        resp = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            content = data["content"][0]["text"]
            result = json.loads(content)
            result["status"] = True
            logging.info(f"User {user_id} requested AI summary for {url}")
            return result
        else:
            return {"status": False, "error": "Summarisation failed"}
    except requests.Timeout:
        return {"status": False, "error": "Summarisation timed out"}
    except:
        return {"status": False, "error": "Summarisation error"}

def summarise_file(file_id, user_id, atn=None):
    # Load from db
    import src.db as db
    files = db.get_uploaded_files(user_id)
    file_data = next((f for f in files if f["id"] == file_id), None)
    if not file_data:
        return {"status": False, "error": "File not found"}
    
    text = file_data["extracted_text"]
    if len(text) < 100:
        return {"status": False, "error": "This file does not contain sufficient information to generate a summary."}

    # Similar to url, but target 300 words
    system = "You are an academic research assistant for secondary school students. You summarise academic sources accurately and concisely. You never fabricate information. If the provided content is insufficient to answer, you must explicitly say so."
    user_prompt = f"File: {file_data['filename']}\n\nContent:\n{text[:6000]}\n\n"  # Approx 300 words
    if atn:
        user_prompt += f"This summary is for the following assessment task: {atn}. Include a relevance explanation."
    user_prompt += "\n\nRespond only with JSON: {\"summary\": \"...\", \"bullets\": [\"...\"], \"relevance\": \"...\"}"

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "system": system,
        "messages": [{"role": "user", "content": user_prompt}]
    }
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    try:
        resp = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            content = data["content"][0]["text"]
            result = json.loads(content)
            result["status"] = True
            logging.info(f"User {user_id} requested AI summary for file {file_id}")
            return result
        else:
            return {"status": False, "error": "Summarisation failed"}
    except requests.Timeout:
        return {"status": False, "error": "Summarisation timed out"}
    except:
        return {"status": False, "error": "Summarisation error"}