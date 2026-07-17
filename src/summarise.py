import os
import requests
import json
import logging
import src.whitelist as whitelist
import src.proxy as proxy
import src.local_ai as local_ai
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_SUMMARISE_MODEL = os.getenv("ANTHROPIC_SUMMARISE_MODEL", "claude-haiku-4-5-20251001")
USE_LOCAL_AI = os.getenv("USE_LOCAL_AI", "0") != "0"


def _use_local():
    return USE_LOCAL_AI or not ANTHROPIC_API_KEY


def _anthropic_request(prompt: str):
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": ANTHROPIC_SUMMARISE_MODEL,
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


def _parse_ai_json_response(content: str) -> dict:
    """Try to parse a JSON object from model output robustly."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Attempt to extract a JSON object from anywhere in the text
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start:end+1])
            except json.JSONDecodeError:
                pass
    return {}


def summarise_url(url, title, atn=None, user_id=None):
    # Allow summarisation requests for any URL; proxy.fetch_source will
    # enforce access rules and return an appropriate error if needed.

    fetched = proxy.fetch_source(url)
    if not fetched["status"]:
        return fetched

    text = fetched.get("text", "")
    if len(text) < 10:
        return {"status": False, "error": "This source does not contain sufficient information to generate a summary (insufficient)."}

    if _use_local():
        return local_ai.summarize_source(text, title or fetched.get("title", ""), atn)

    user_prompt = f"Title: {title}\n\nContent:\n{text[:4000]}\n\n"
    if atn:
        user_prompt += f"This summary is for the following assessment task: {atn}. Include a relevance explanation."
    user_prompt += "\n\nRespond only with JSON: {\"summary\": \"...\", \"bullets\": [\"...\"], \"relevance\": \"...\"}"

    try:
        content = _anthropic_request(user_prompt)
        result = _parse_ai_json_response(content)
        if not result:
            raise ValueError('Unable to parse model response')
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
        result = _parse_ai_json_response(content)
        if not result:
            raise ValueError('Unable to parse model response')
        result["status"] = True
        logging.info(f"User {user_id} requested AI summary for file {file_id}")
        return result
    except requests.Timeout:
        return {"status": False, "error": "Summarisation timed out"}
    except Exception:
        return {"status": False, "error": "Summarisation error"}


def summarise_search_results(query: str, results: list[dict], atn: str | None = None) -> str:
    # Use only the top-ranked result from each whitelisted source for summarisation.
    rank_one_results = []
    seen_domains = set()
    for r in results:
        if r.get('whitelist_rank') == 1:
            domain = whitelist.get_domain(r.get('source_url', '') or '')
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                rank_one_results.append(r)

    if not rank_one_results:
        # Fallback to the first unique source if no whitelist rank is assigned.
        seen_sources = set()
        for r in results:
            source = r.get('source_name', '').lower()
            if source in seen_sources:
                continue
            seen_sources.add(source)
            rank_one_results.append(r)

    if _use_local():
        try:
            return local_ai.summarize_search_results(query, rank_one_results, atn)
        except Exception:
            pass

    prompt = "You are an academic research assistant for secondary school students. Summarise the most relevant search results clearly and concisely in 2-3 sentences.\n\n"
    if atn:
        prompt = f"For the assessment task: {atn}\n\n" + prompt
    prompt += f"Query: {query}\n\n"
    prompt += "Top search results:\n"

    for result in rank_one_results[:10]:
        title = (result.get('title') or 'Untitled').strip()
        description = (result.get('description') or '').strip()
        source = result.get('source_name') or result.get('source_url') or 'Unknown source'
        prompt += f"- {title} ({source}): {description}\n"

    prompt += "\nSummary:"

    try:
        content = _anthropic_request(prompt)
        summary = content.strip()
        if not summary:
            raise ValueError('Empty summary')
        return summary
    except Exception:
        # Deterministic fallback summary if API fails.
        snippets = []
        for result in rank_one_results[:5]:
            title = (result.get('title') or 'Untitled').strip()
            description = (result.get('description') or '').strip()
            if description:
                snippets.append(f"{title}: {description.split('.')[0]}")
        if snippets:
            return ' '.join(snippets[:3])
        return 'Unable to generate a coherent summary from the available search results.'
