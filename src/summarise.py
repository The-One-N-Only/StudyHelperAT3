import os
import requests
import json
import logging
import src.whitelist as whitelist
import src.proxy as proxy

AI_NOT_CONFIGURED_ERROR = (
    "Alexander is not configured. Add ANTHROPIC_API_KEY and restart StudyLib."
)
AI_PROVIDER_ERROR = "Alexander could not reach the AI service. Try again shortly."
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_SUMMARISE_MODEL = os.getenv("ANTHROPIC_SUMMARISE_MODEL", "claude-haiku-4-5-20251001")


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


def summarise_url(url, title=None, atn=None, user_id=None) -> dict:
    if not ANTHROPIC_API_KEY:
        return {"status": False, "error": AI_NOT_CONFIGURED_ERROR}

    if not whitelist.is_allowed(url):
        raise ValueError("URL not allowed")

    fetched = proxy.fetch_source(url)
    if not fetched["status"]:
        return fetched

    text = fetched.get("text", "")
    if len(text) < 100:
        return {"status": False, "error": "This source contains insufficient information to generate a summary."}

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
        if user_id is not None:
            logging.info(f"User {user_id} requested AI summary for {url}")
        return result
    except Exception:
        logging.exception("Anthropic request failed while summarising URL")
        return {"status": False, "error": AI_PROVIDER_ERROR}


def summarise_file(file_id, user_id, atn=None) -> dict:
    if not ANTHROPIC_API_KEY:
        return {"status": False, "error": AI_NOT_CONFIGURED_ERROR}

    import src.db as db
    files = db.get_uploaded_files(user_id)
    file_data = next((f for f in files if f["id"] == file_id), None)
    if not file_data:
        return {"status": False, "error": "File not found"}

    text = file_data["extracted_text"]
    if len(text) < 100:
        return {"status": False, "error": "This file contains insufficient information to generate a summary."}

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
    except Exception:
        logging.exception("Anthropic request failed while summarising file")
        return {"status": False, "error": AI_PROVIDER_ERROR}


def summarise_search_results(query: str, results: list[dict], atn: str | None = None) -> dict:
    if not ANTHROPIC_API_KEY:
        return {"status": False, "error": AI_NOT_CONFIGURED_ERROR}

    summary_results = []
    seen_domains = set()
    for result in results:
        if result.get("whitelist_rank") != 1:
            continue
        domain = whitelist.get_domain(result.get("source_url", "") or "")
        if domain and domain not in seen_domains:
            seen_domains.add(domain)
            summary_results.append(result)

    if not summary_results:
        seen_sources = set()
        for result in results:
            source = (result.get("source_name") or "").strip().casefold()
            if source in seen_sources:
                continue
            seen_sources.add(source)
            summary_results.append(result)

    prompt = "Briefly summarise these search results in 2-3 sentences. Be concise and factual.\n\n"
    if atn:
        prompt = f"For the following assessment task: {atn}\n\n" + prompt
    prompt += "Search results:\n"
    for result in summary_results[:10]:
        title = result.get('title', 'Untitled')
        description = result.get('description', '').strip()
        prompt += f"- {title}: {description}\n"
    prompt += "\nSummary:"

    try:
        content = _anthropic_request(prompt)
        return {"status": True, "summary": content.strip()}
    except Exception:
        logging.exception("Anthropic request failed while summarising search results")
        snippets = []
        for result in summary_results[:5]:
            title = (result.get("title") or "Untitled").strip()
            description = (result.get("description") or "").strip()
            if description:
                snippets.append(f"{title}: {description.split('.', 1)[0].strip()}")
        if snippets:
            return {"status": True, "summary": " ".join(snippets[:3])}
        return {"status": False, "error": AI_PROVIDER_ERROR}
