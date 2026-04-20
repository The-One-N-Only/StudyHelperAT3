import anthropic
import os
from typing import Optional
import src.db as db
import src.proxy as proxy
import src.whitelist as whitelist
import logging
from urllib.parse import quote

# Initialize Anthropic client
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def search_files_for_context(user_id: int, query: str, num_results: int = 5) -> dict:
    """
    Search uploaded files for content relevant to the query.
    Returns relevant passages with file references.
    """
    try:
        uploaded_files = db.get_uploaded_files(user_id)
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


def answer_prompt(prompt: str, user_id: int, search_web: bool = True, atn: Optional[str] = None) -> dict:
    """
    Answer a user prompt using information from uploaded files and optionally web sources.
    
    Args:
        prompt: The user's question or prompt
        user_id: The user ID
        search_web: Whether to search Wikipedia for additional context
        atn: Optional assessment task/note for context
    
    Returns:
        Dict with answer, sources used, and status
    """
    try:
        # Collect context from files
        file_context = search_files_for_context(user_id, prompt, num_results=3)
        context_text = file_context["context"]
        all_sources = file_context["sources"].copy()
        
        # Optionally search web
        if search_web:
            wiki_context = search_wikipedia_for_context(prompt)
            if wiki_context["context"]:
                context_text += wiki_context["context"]
                if wiki_context["source"]:
                    all_sources.append(wiki_context["source"])
        
        # Build system prompt
        system_prompt = """You are an academic research assistant for secondary school students. 
You provide accurate, well-reasoned answers based on the information provided. 
You never fabricate information or cite sources not provided in the context.
If the provided information is insufficient to answer the question, clearly state that.
Format your answer clearly with key points where appropriate."""
        
        if atn:
            system_prompt += f"\n\nAssessment Task Context: {atn}"
        
        # Build user message with context
        user_message = f"{context_text}\n---\n\nQuestion: {prompt}\n\nPlease answer this question based on the above information."
        
        # Call Claude API
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
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
    
    except Exception as e:
        logging.error(f"Error answering prompt for user {user_id}: {str(e)}")
        return {
            "status": False,
            "error": f"Failed to generate answer: {str(e)}",
            "answer": None
        }


def chat_with_sources(messages: list, user_id: int, atn: Optional[str] = None) -> dict:
    """
    Multi-turn conversation with context from uploaded files and web.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        user_id: The user ID
        atn: Optional assessment task/note for context
    
    Returns:
        Dict with response and sources used
    """
    try:
        # Get initial context from the last user message
        last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        
        file_context = search_files_for_context(user_id, last_user_message, num_results=2)
        context_text = file_context["context"]
        all_sources = file_context["sources"].copy()
        
        system_prompt = """You are an academic research assistant for secondary school students.
You provide accurate, well-reasoned answers based on the information provided.
You never fabricate information or cite sources not provided in the context.
Engage naturally in conversation while maintaining academic rigor."""
        
        if atn:
            system_prompt += f"\n\nAssessment Task Context: {atn}"
        
        if context_text:
            system_prompt += f"\n\nContext from your files:\n{context_text}"
        
        # Call Claude API with message history
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            system=system_prompt,
            messages=messages
        )
        
        response_text = response.content[0].text
        
        logging.info(f"User {user_id} had multi-turn conversation")
        
        return {
            "status": True,
            "response": response_text,
            "sources": all_sources
        }
    
    except Exception as e:
        logging.error(f"Error in chat for user {user_id}: {str(e)}")
        return {
            "status": False,
            "error": f"Failed to generate response: {str(e)}"
        }
