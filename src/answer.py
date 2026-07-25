from __future__ import annotations

import os
import logging
import re
from typing import Optional
from urllib.parse import quote

import anthropic

import src.db as db
import src.proxy as proxy
import src.search as search
import src.whitelist as whitelist
import src.pubmed as pubmed

AI_NOT_CONFIGURED_ERROR = (
    "Alexander is not configured. Add ANTHROPIC_API_KEY and restart StudyLib."
)
AI_PROVIDER_ERROR = "Alexander could not reach the AI service. Try again shortly."
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

def _strip_html(text: str) -> str:
    """Remove HTML tags from text to create clean plain-text context."""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    return clean.strip()


def gather_workspace_notes_context(workspace_id: int, user_id: int, query: str) -> dict:
    """Fetch workspace notes and extract context relevant to the query."""
    notes = db.get_workspace_notes(workspace_id, user_id)
    if not notes:
        return {"status": True, "context": "", "sources": []}

    context_parts = []
    keywords = query.lower().split()

    for note in notes:
        title = note.get("title", "Untitled")
        content = note.get("content", "")
        if not content:
            continue

        clean_content = _strip_html(content)

        score = sum(clean_content.lower().count(kw) for kw in keywords)
        if score > 0 or len(notes) <= 2:
            truncated = clean_content[:2000]
            if len(clean_content) > 2000:
                truncated += "..."
            context_parts.append(
                f"**Note titled '{title}':**\n{truncated}"
            )

    if context_parts:
        context_text = "**Information from your workspace notes:**\n\n" + "\n\n".join(context_parts) + "\n\n"
        return {
            "status": True,
            "context": context_text,
            "sources": [{"type": "workspace_note", "title": n["title"]} for n in notes if n.get("content")]
        }

    return {"status": True, "context": "", "sources": []}


def search_files_for_context(user_id: int, query: str, num_results: int = 5, workspace_id: Optional[int] = None) -> dict:
    """
    Search uploaded files for content relevant to the query.
    When workspace_id is provided, only searches files in that workspace.
    Returns relevant passages with file references.
    """
    try:
        uploaded_files = db.get_workspace_uploaded_files(workspace_id, user_id) if workspace_id else db.get_uploaded_files(user_id)
        if not uploaded_files:
            return {"status": True, "context": "", "sources": []}
        
        # Simple relevance scoring based on keyword matching
        relevant_passages = []
        keywords = query.lower().split()
        
        for file_data in uploaded_files:
            text = file_data.get("extracted_text", "").lower()
            filename = file_data.get("filename", "Unknown")
            file_id = file_data.get("id")
            
            # Calculate relevance score
            score = sum(text.count(keyword) for keyword in keywords)
            
            if score > 0:
                # Extract relevant passages (sentences containing keywords)
                sentences = text.split('.')
                relevant_sentences = []
                for sentence in sentences:
                    if any(keyword in sentence for keyword in keywords):
                        relevant_sentences.append(sentence.strip())
                
                if relevant_sentences:
                    # Limit to first 1000 chars of relevant content per file
                    passage = ". ".join(relevant_sentences[:5])[:1000]
                    relevant_passages.append({
                        "file_id": file_id,
                        "filename": filename,
                        "passage": passage,
                        "score": score
                    })
        
        # Sort by relevance score and limit results
        relevant_passages.sort(key=lambda x: x["score"], reverse=True)
        relevant_passages = relevant_passages[:num_results]
        
        # Format context for Claude
        context_text = ""
        sources = []
        if relevant_passages:
            context_text = "**Information from your uploaded files:**\n\n"
            for item in relevant_passages:
                context_text += f"From '{item['filename']}':\n{item['passage']}\n\n"
                sources.append({
                    "type": "file",
                    "filename": item["filename"],
                    "file_id": item["file_id"]
                })
        
        return {
            "status": True,
            "context": context_text,
            "sources": sources
        }
    except Exception as e:
        logging.error(f"Error searching files for user {user_id}: {str(e)}")
        return {"status": True, "context": "", "sources": []}


def search_wikipedia_for_context(query: str) -> dict:
    """
    Search Wikipedia for information relevant to the query.
    """
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(query)}"
        headers = {"User-Agent": "StudyLib/1.0 (Academic Research Assistant)"}
        import requests
        
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract", "")
            title = data.get("title", "")
            content_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            
            if extract and len(extract) > 50:
                context = f"**Information from Wikipedia ({title}):**\n{extract}\n\n"
                return {
                    "status": True,
                    "context": context,
                    "source": {
                        "type": "wikipedia",
                        "title": title,
                        "url": content_url
                    }
                }
        return {"status": True, "context": "", "source": None}
    except Exception as e:
        logging.error(f"Error searching Wikipedia: {str(e)}")
        return {"status": True, "context": "", "source": None}


def gather_whitelisted_context(query: str, user_id: int, num_results: int = 3) -> dict:
    context_text = ""
    sources = []

    wiki_context = search_wikipedia_for_context(query)
    if wiki_context["context"]:
        context_text += wiki_context["context"]
        if wiki_context["source"]:
            sources.append(wiki_context["source"])

    try:
        gbooks_results = search.gbooks(query, num_results, {}, user_id=user_id)
        for item in gbooks_results[:2]:
            title = item.get("title", "")
            description = item.get("description", "")
            url = item.get("source_url", "")
            if description:
                context_text += f"**Information from Google Books ({title}):**\n{description}\n\n"
                sources.append({"type": "gbooks", "title": title, "url": url})
    except Exception:
        pass

    try:
        pubmed_results = pubmed.search(query, num_results, [], None, None, user_id=user_id)
        for item in pubmed_results[:2]:
            title = item.get("title", "")
            description = item.get("description", "")
            url = item.get("source_url", "")
            if description:
                context_text += f"**Information from PubMed ({title}):**\n{description}\n\n"
                sources.append({"type": "pubmed", "title": title, "url": url})
    except Exception:
        pass

    return {
        "status": True,
        "context": context_text,
        "sources": sources
    }


PERSONA_PROMPTS = {
    "formal": (
        "You are an academic research assistant for secondary school students. "
        "Use formal academic language, cite sources rigorously with inline citations [1], [2], etc. "
        "Structure your answers with clear thesis statements and evidence."
    ),
    "casual": (
        "You are a friendly study buddy helping a secondary school student. "
        "Use simple, conversational language. Encourage the student and make learning feel accessible. "
        "Cite sources with inline citations [1], [2] etc."
    ),
    "socratic": (
        "You are a Socratic tutor for a secondary school student. "
        "Instead of giving direct answers, ask guiding questions that help the student discover the answer themselves. "
        "Draw from the provided sources to inform your questions."
    ),
    "tutor": (
        "You are a patient one-on-one tutor for a secondary school student. "
        "Explain concepts step by step, check for understanding, and build upon foundational knowledge. "
        "Cite sources with inline citations [1], [2] etc."
    ),
}


def _build_system_prompt(atn: Optional[str] = None, context_text: str = "", persona: str = "formal") -> str:
    base = PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["formal"])
    system_prompt = base + (
        " You never fabricate information or cite sources not provided in the context."
        " Use inline citations like [1], [2] to reference sources."
        " If the provided information is insufficient, clearly state that."
        " Format your answer clearly with key points where appropriate."
    )
    if atn:
        system_prompt += f"\n\nAssessment Task Context: {atn}"
    if context_text:
        system_prompt += f"\n\nContext from your files and sources is provided below."
    return system_prompt


def answer_prompt(prompt: str, user_id: int, search_web: bool = True, atn: Optional[str] = None, workspace_id: Optional[int] = None, persona: str = "formal") -> dict:
    """
    Answer a user prompt using information from uploaded files and optionally web sources.
    
    Args:
        prompt: The user's question or prompt
        user_id: The user ID
        search_web: Whether to search Wikipedia for additional context
        atn: Optional assessment task/note for context
        workspace_id: Optional workspace ID to include workspace notes as context
    
    Returns:
        Dict with answer, sources used, and status
    """
    if client is None:
        return {
            "status": False,
            "error": AI_NOT_CONFIGURED_ERROR
        }

    try:
        # Collect context from files
        file_context = search_files_for_context(user_id, prompt, num_results=3, workspace_id=workspace_id)
        context_text = file_context["context"]
        all_sources = file_context["sources"].copy()

        # Collect context from workspace notes if applicable
        if workspace_id:
            notes_context = gather_workspace_notes_context(workspace_id, user_id, prompt)
            if notes_context["context"]:
                context_text += notes_context["context"]
                all_sources.extend(notes_context["sources"])
        
        # Optionally search web and whitelisted sources (skip when in workspace context)
        if search_web and not workspace_id:
            web_context = gather_whitelisted_context(prompt, user_id)
            if web_context["context"]:
                context_text += web_context["context"]
                all_sources.extend(web_context["sources"])
        
        system_prompt = _build_system_prompt(atn, context_text, persona)

        user_message = f"{context_text}\n---\n\nQuestion: {prompt}\n\nPlease answer this question based on the above information."

        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        answer_text = message.content[0].text
        
        logging.info(f"User {user_id} received AI answer for prompt: {prompt[:50]}")
        
        return {
            "status": True,
            "answer": answer_text,
            "sources": all_sources,
            "context_used": context_text
        }
    
    except Exception:
        logging.exception("Anthropic request failed while answering prompt for user %s", user_id)
        return {
            "status": False,
            "error": AI_PROVIDER_ERROR
        }


def _parse_citations(text: str, sources: list) -> tuple[str, list]:
    """Parse citation markers like [1], [2] from response text and build citation mapping."""
    citations = []
    seen = set()
    for match in re.finditer(r'\[(\d+)\]', text):
        idx = int(match.group(1))
        if idx not in seen and idx > 0 and idx <= len(sources):
            seen.add(idx)
            source = sources[idx - 1]
            citations.append({
                "index": idx,
                "title": source.get("title") or source.get("filename", "Source"),
                "source_url": source.get("url") or source.get("source_url", ""),
                "snippet": source.get("passage", "")[:200] if source.get("passage") else "",
            })
    return text, citations


def chat_with_sources(messages: list, user_id: int, atn: Optional[str] = None, workspace_id: Optional[int] = None, persona: str = "formal") -> dict:
    """
    Multi-turn conversation with context from uploaded files and web.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        user_id: The user ID
        atn: Optional assessment task/note for context
        workspace_id: Optional workspace ID to include workspace notes as context
        persona: AI persona/tone (formal, casual, socratic, tutor)
    
    Returns:
        Dict with response, sources used, and citations
    """
    if client is None:
        return {
            "status": False,
            "error": AI_NOT_CONFIGURED_ERROR
        }

    try:
        # Get initial context from the last user message
        last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        
        file_context = search_files_for_context(user_id, last_user_message, num_results=2, workspace_id=workspace_id)
        context_text = file_context["context"]
        all_sources = file_context["sources"].copy()

        if workspace_id:
            notes_context = gather_workspace_notes_context(workspace_id, user_id, last_user_message)
            if notes_context["context"]:
                context_text += notes_context["context"]
                all_sources.extend(notes_context["sources"])
        else:
            web_context = gather_whitelisted_context(last_user_message, user_id)
            if web_context["context"]:
                context_text += web_context["context"]
                all_sources.extend(web_context["sources"])
        
        # Map sources with indices for citation
        source_refs = ""
        for i, s in enumerate(all_sources, 1):
            title = s.get("title") or s.get("filename", "Source")
            url = s.get("url") or s.get("source_url", "")
            source_refs += f"[{i}] {title} - {url}\n"

        system_prompt = _build_system_prompt(atn, context_text, persona)

        if source_refs:
            system_prompt += f"\n\nAvailable sources (cite by number):\n{source_refs}"

        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=messages
        )
        response_text = response.content[0].text
        
        # Parse citations from response
        response_text, citations = _parse_citations(response_text, all_sources)
        
        logging.info(f"User {user_id} had multi-turn conversation")
        
        return {
            "status": True,
            "response": response_text,
            "sources": all_sources,
            "citations": citations,
        }
    
    except Exception:
        logging.exception("Anthropic chat request failed for user %s", user_id)
        return {
            "status": False,
            "error": AI_PROVIDER_ERROR
        }


def generate_follow_up_questions(conversation_history: list, workspace_context: str = "") -> list:
    """Suggest 3 follow-up questions based on the last AI response and workspace context."""
    if client is None:
        return []
    try:
        last_exchange = ""
        for msg in reversed(conversation_history[-4:]):
            role = msg.get("role", "")
            content = msg.get("content", "")
            last_exchange += f"{role.upper()}: {content}\n"

        prompt = (
            f"Based on this conversation, suggest 3 short follow-up questions the student might want to ask.\n\n"
            f"{last_exchange}\n"
            f"Workspace context: {workspace_context[:500]}\n\n"
            f"Return ONLY a JSON array of 3 short question strings, nothing else."
        )
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=300,
            system="You are a helpful academic tutor. Suggest follow-up questions as a JSON array.",
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text
        try:
            questions = json.loads(text)
            if isinstance(questions, list) and len(questions) <= 5:
                return questions[:3]
        except json.JSONDecodeError:
            # Try to extract array from text
            import re
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                try:
                    questions = json.loads(match.group())
                    if isinstance(questions, list):
                        return questions[:3]
                except json.JSONDecodeError:
                    pass
        return []
    except Exception:
        logging.exception("Failed to generate follow-up questions")
        return []


def synthesize_sources(source_texts: list[dict], instruction: str) -> dict:
    """
    Multi-document synthesis of provided sources.
    
    Args:
        source_texts: List of dicts with 'title', 'source', 'content' keys
        instruction: One of 'compare', 'contradictions', 'themes', 'argument'
    
    Returns:
        Dict with status and synthesis text
    """
    if client is None:
        return {"status": False, "error": AI_NOT_CONFIGURED_ERROR}

    instruction_prompts = {
        "themes": "Summarize the key themes across these sources. Identify common topics and significant ideas.",
        "compare": "Compare and contrast the sources. Highlight similarities, differences, and unique perspectives.",
        "contradictions": "Identify any contradictions, disagreements, or conflicting findings between these sources.",
        "argument": "Build a structured argument for or against the main thesis presented in these sources. Use evidence from the sources to support each point.",
    }
    sys_instruction = instruction_prompts.get(instruction, instruction_prompts["themes"])

    try:
        sources_text = ""
        for i, s in enumerate(source_texts, 1):
            title = s.get("title", "Untitled")
            content = s.get("content", "")[:3000]
            sources_text += f"--- Source {i}: {title} ---\n{content}\n\n"

        prompt = (
            f"{sys_instruction}\n\n"
            f"Sources:\n{sources_text}\n\n"
            f"Provide a structured synthesis with section headings. Be thorough and cite sources by number."
        )
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=3072,
            system="You are an academic synthesis assistant. Create well-structured multi-source analyses with clear section headings.",
            messages=[{"role": "user", "content": prompt}]
        )
        return {"status": True, "synthesis": response.content[0].text}
    except Exception:
        logging.exception("Synthesis failed")
        return {"status": False, "error": AI_PROVIDER_ERROR}


def generate_study_guide(workspace_id: int, user_id: int) -> dict:
    """Auto-generate a study guide from all sources in a workspace."""
    if client is None:
        return {"status": False, "error": AI_NOT_CONFIGURED_ERROR}
    try:
        items = db.get_workspace_items(user_id, workspace_id)
        if not items:
            return {"status": False, "error": "No sources in workspace to generate study guide from."}

        sources_text = ""
        for i, item in enumerate(items, 1):
            title = item.get("title", "Untitled")
            summary = item.get("summary", "")[:500]
            content = item.get("abstract", "")[:2000]
            sources_text += f"--- Source {i}: {title} ---\nSummary: {summary}\nContent: {content}\n\n"

        prompt = (
            f"Create a comprehensive study guide from these sources. Include:\n"
            f"1. Key concepts with definitions\n"
            f"2. Important dates and figures\n"
            f"3. Connections between topics\n"
            f"4. 5 practice questions with answers\n\n"
            f"Sources:\n{sources_text}\n\n"
            f"Format as structured markdown with clear headings."
        )
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system="You are an expert study guide creator for secondary school students. Create clear, structured study guides in markdown.",
            messages=[{"role": "user", "content": prompt}]
        )
        return {"status": True, "study_guide": response.content[0].text}
    except Exception:
        logging.exception("Study guide generation failed")
        return {"status": False, "error": AI_PROVIDER_ERROR}


def generate_essay_outline(workspace_id: int, user_id: int, thesis_statement: str) -> dict:
    """Generate a detailed essay outline from workspace sources based on a thesis."""
    if client is None:
        return {"status": False, "error": AI_NOT_CONFIGURED_ERROR}
    try:
        items = db.get_workspace_items(user_id, workspace_id)
        if not items:
            return {"status": False, "error": "No sources in workspace to generate outline from."}

        sources_text = ""
        for i, item in enumerate(items, 1):
            title = item.get("title", "Untitled")
            summary = item.get("summary", "")[:500]
            content = item.get("abstract", "")[:2000]
            sources_text += f"--- Source {i}: {title} ---\nSummary: {summary}\nContent: {content}\n\n"

        prompt = (
            f"Thesis statement: {thesis_statement}\n\n"
            f"Generate a detailed essay outline based on these sources. Include:\n"
            f"1. Thesis restatement\n"
            f"2. 3-5 main arguments with supporting evidence from sources\n"
            f"3. Counterarguments with rebuttals\n"
            f"4. Conclusion\n\n"
            f"Sources:\n{sources_text}\n\n"
            f"Format as structured markdown with clear headings and bullet points."
        )
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system="You are an expert essay outline generator. Create detailed, well-structured outlines with evidence from provided sources.",
            messages=[{"role": "user", "content": prompt}]
        )
        return {"status": True, "outline": response.content[0].text}
    except Exception:
        logging.exception("Essay outline generation failed")
        return {"status": False, "error": AI_PROVIDER_ERROR}
