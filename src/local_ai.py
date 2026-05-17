import os
import re
import logging
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = os.getenv("LOCAL_AI_MODEL", "distilgpt2")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_TOKENIZER = None
_MODEL = None


def _load_model():
    global _TOKENIZER, _MODEL
    if _MODEL is not None and _TOKENIZER is not None:
        return
    logging.info(f"Loading local AI model: {MODEL_NAME} on {DEVICE}")
    _TOKENIZER = AutoTokenizer.from_pretrained(MODEL_NAME)
    if _TOKENIZER.pad_token is None:
        _TOKENIZER.pad_token = _TOKENIZER.eos_token
    _MODEL = AutoModelForCausalLM.from_pretrained(MODEL_NAME)
    _MODEL.to(DEVICE)


def _generate_text(prompt: str, max_new_tokens: int = 120, temperature: float = 0.7, top_p: float = 0.9) -> str:
    _load_model()
    encoded = _TOKENIZER(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=min(1024, _TOKENIZER.model_max_length),
        return_attention_mask=True,
    )
    input_ids = encoded["input_ids"].to(DEVICE)
    attention_mask = encoded["attention_mask"].to(DEVICE)

    with torch.no_grad():
        outputs = _MODEL.generate(
            input_ids,
            attention_mask=attention_mask,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
            pad_token_id=_TOKENIZER.pad_token_id,
            eos_token_id=_TOKENIZER.eos_token_id,
        )
    text = _TOKENIZER.decode(outputs[0], skip_special_tokens=True)
    return text.strip()


def _extract_bullets(text: str) -> list[str]:
    bullets = re.findall(r"^[\-\u2022\*]\s*(.+)$", text, flags=re.MULTILINE)
    if bullets:
        return [b.strip() for b in bullets][:5]
    # Fallback to sentence split
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\\s+", text) if s.strip()]
    return sentences[:3]


def _extract_section(text: str, label: str) -> str:
    match = re.search(rf"{label}\s*:\s*(.+?)(?:\n\n|$)", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip().replace("\n", " ")
    return ""


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def summarize_source(text: str, title: str = "", atn: str | None = None) -> dict:
    content = _normalize_text(text)
    source_title = title.strip() or "Source material"
    prompt = (
        "You are an academic research assistant for secondary school students.\n"
        "Summarise the following source accurately and concisely. Do not invent facts.\n"
        f"Title: {source_title}\n"
        f"Content: {content[:1400]}\n"
        "\nRespond with a short summary sentence, three clear bullet points, and a one-sentence relevance statement.\n"
        "Use the following format:\nSummary: ...\nBullets:\n- ...\n- ...\n- ...\nRelevance: ...\n"
    )
    if atn:
        prompt += f"Assessment task context: {atn}\n"

    response = _generate_text(prompt, max_new_tokens=180, temperature=0.3, top_p=0.95)
    summary = _extract_section(response, "Summary") or response.split("\n", 1)[0].strip()
    bullets = _extract_bullets(response)
    relevance = _extract_section(response, "Relevance")
    if not bullets:
        # If bullets cannot be found, try to infer from the first few sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\\s+", response) if s.strip()]
        bullets = sentences[1:4] if len(sentences) > 1 else sentences[:3]
    if not relevance and len(bullets) > 0:
        relevance = f"This source is relevant because it helps explain key ideas in the topic." 

    return {
        "status": True,
        "summary": summary,
        "bullets": bullets,
        "relevance": relevance,
        "raw": response,
    }


def summarize_search_results(query: str, results: list[dict], atn: str | None = None) -> str:
    lines = []
    for result in results[:8]:
        title = result.get("title", "Untitled")
        description = result.get("description", "").strip()
        lines.append(f"{title}: {description}")
    
    # Build a clean prompt that doesn't echo back the preamble
    prompt = "Briefly summarise these search results in 2-3 sentences. Be concise and factual.\n\nSearch results:\n"
    prompt += "\n".join(lines)
    prompt += "\n\nSummary:"
    
    if atn:
        prompt = f"For the assessment task: {atn}\n\n" + prompt
    
    response = _generate_text(prompt, max_new_tokens=150, temperature=0.3, top_p=0.95)
    # Extract only the summary portion (after "Summary:" or similar markers)
    summary = response.strip()
    # Remove any echoed back instructions or prompt text
    for marker in ["Search results:", "Assessment task", "You are an"]:
        if marker in summary:
            # Keep only the part after the marker
            idx = summary.find(marker)
            if idx > -1:
                summary = summary[idx + len(marker):].strip()
    # Clean up any remaining artifacts
    summary = summary.replace("Summary:", "").strip()
    if len(summary) > 500:
        summary = summary[:500].rsplit(" ", 1)[0] + "..."
    return summary


def answer_with_context(question: str, context: str, atn: str | None = None) -> str:
    safe_context = _normalize_text(context)[:1600]
    prompt = (
        "You are an academic research assistant for secondary school students.\n"
        "Answer the question using only the information in the provided context.\n"
        "If the context does not contain enough information, say that clearly.\n"
    )
    if atn:
        prompt += f"Assessment task context: {atn}\n"
    prompt += f"\nContext:\n{safe_context}\n\nQuestion: {question}\nAnswer:"
    response = _generate_text(prompt, max_new_tokens=220, temperature=0.5, top_p=0.95)
    return _normalize_text(response)


def chat_with_context(messages: list[dict], context: str, atn: str | None = None) -> str:
    safe_context = _normalize_text(context)[:1600]
    prompt = (
        "You are an academic research assistant for secondary school students.\n"
        "Answer the conversation using only the provided context and do not invent facts.\n"
    )
    if atn:
        prompt += f"Assessment task context: {atn}\n"
    if safe_context:
        prompt += f"\nContext:\n{safe_context}\n"
    prompt += "\nConversation:\n"
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "").strip()
        prompt += f"{role.capitalize()}: {content}\n"
    prompt += "Assistant:"
    response = _generate_text(prompt, max_new_tokens=220, temperature=0.5, top_p=0.95)
    return _normalize_text(response)
