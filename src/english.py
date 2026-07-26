"""English subject-specific tools: related texts, literary criticism search."""

import logging

from . import search as search_mod

logger = logging.getLogger(__name__)

# Prescribed texts database (common HSC texts)
PRESCRIBED_TEXTS = {
    "1984": {"author": "George Orwell", "type": "prose fiction", "module": "Textual Conversations", "elective": "Comparative Study"},
    "The Tempest": {"author": "William Shakespeare", "type": "drama", "module": "Textual Conversations", "elective": "Comparative Study"},
    "Frankenstein": {"author": "Mary Shelley", "type": "prose fiction", "module": "Textual Conversations", "elective": "Comparative Study"},
    "The Great Gatsby": {"author": "F. Scott Fitzgerald", "type": "prose fiction", "module": "Textual Conversations", "elective": "Comparative Study"},
    "Othello": {"author": "William Shakespeare", "type": "drama", "module": "Critical Study", "elective": "N/A"},
    "Wuthering Heights": {"author": "Emily Brontë", "type": "prose fiction", "module": "Textual Conversations", "elective": "Comparative Study"},
    "The Merchant of Venice": {"author": "William Shakespeare", "type": "drama", "module": "Common Module", "elective": "N/A"},
    "The Crucible": {"author": "Arthur Miller", "type": "drama", "module": "Common Module", "elective": "N/A"},
    "A Doll's House": {"author": "Henrik Ibsen", "type": "drama", "module": "Critical Study", "elective": "N/A"},
    "The Poetry of Sylvia Plath": {"author": "Sylvia Plath", "type": "poetry", "module": "Critical Study", "elective": "N/A"},
    "The Poetry of Robert Frost": {"author": "Robert Frost", "type": "poetry", "module": "Textual Conversations", "elective": "Comparative Study"},
    "The Poetry of T.S. Eliot": {"author": "T.S. Eliot", "type": "poetry", "module": "Critical Study", "elective": "N/A"},
}

def find_prescribed_text(query: str) -> dict | None:
    """Search for a prescribed text by title or author."""
    query_lower = query.lower()
    for title, info in PRESCRIBED_TEXTS.items():
        if query_lower in title.lower() or query_lower in info["author"].lower():
            return {"title": title, **info}
    return None

def find_related_texts(prescribed_title: str, themes: list[str] = None) -> list[dict]:
    """Find related texts thematically linked to a prescribed text using Google Books."""
    text_info = PRESCRIBED_TEXTS.get(prescribed_title)
    if not text_info:
        return []

    themes_str = ", ".join(themes) if themes else "themes of " + prescribed_title
    search_query = f"related texts {text_info['author']} {themes_str} literary analysis"

    results = search_mod.gbooks(search_query, num_results=5)
    return results

def get_literary_criticism(text_title: str, author: str) -> list[dict]:
    """Search for literary criticism on a text using Semantic Scholar."""
    try:
        query = f"{text_title} {author} literary criticism analysis"
        from . import semantic_scholar
        papers = semantic_scholar.search_papers(query, limit=8)
        return papers
    except Exception as e:
        logger.error(f"Literary criticism search failed: {e}")
        return []
