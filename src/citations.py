import json


def format_apa(title, source_name, url, author=None, year=None, authors=None, journal=None, volume=None, issue=None, doi=None):
    """
    Format citation in APA style.

    Args:
        title: Article/book title
        source_name: Source name (e.g., 'PubMed', 'Wikipedia')
        url: Source URL
        author: Single author name (fallback)
        year: Publication year
        authors: JSON string of author list (for PubMed)
        journal: Journal name (for PubMed)
        volume: Journal volume (for PubMed)
        issue: Journal issue (for PubMed)
        doi: Digital Object Identifier (for PubMed)
    """
    # Handle PubMed format with full author and journal info
    if source_name.lower() == 'pubmed' and authors and journal:
        try:
            author_list = json.loads(authors) if isinstance(authors, str) else authors
            # Format authors for APA (up to 20 authors, then et al.)
            if author_list:
                if len(author_list) > 20:
                    author_str = ", ".join(author_list[:20]) + ", et al."
                else:
                    author_str = ", ".join(author_list)
            else:
                author_str = journal
        except (json.JSONDecodeError, TypeError):
            author_str = journal

        # Build journal info
        journal_info = journal
        if volume:
            journal_info += f", {volume}"
        if issue:
            journal_info += f"({issue})"

        citation = f"{author_str} ({year}). {title}. {journal_info}."

        if doi:
            citation += f" https://doi.org/{doi}"
        else:
            citation += f" Retrieved from {url}"

        return citation

    # Fallback to original format
    if author and year:
        return f"{author}, A. ({year}). {title}. {source_name}. {url}"
    else:
        return f"{source_name}. (n.d.). {title}. Retrieved from {url}"


def format_harvard(title, source_name, url, author=None, year=None, authors=None, journal=None, volume=None, issue=None, doi=None):
    """
    Format citation in Harvard style.

    Args:
        title: Article/book title
        source_name: Source name (e.g., 'PubMed', 'Wikipedia')
        url: Source URL
        author: Single author name (fallback)
        year: Publication year
        authors: JSON string of author list (for PubMed)
        journal: Journal name (for PubMed)
        volume: Journal volume (for PubMed)
        issue: Journal issue (for PubMed)
        doi: Digital Object Identifier (for PubMed)
    """
    # Handle PubMed format
    if source_name.lower() == 'pubmed' and authors and journal:
        try:
            author_list = json.loads(authors) if isinstance(authors, str) else authors
            if author_list:
                if len(author_list) > 1:
                    author_str = author_list[0] + " et al."
                else:
                    author_str = author_list[0]
            else:
                author_str = journal
        except (json.JSONDecodeError, TypeError):
            author_str = journal

        # Build journal info
        journal_info = journal
        if volume:
            journal_info += f", {volume}"
        if issue:
            journal_info += f"({issue})"

        url_info = f"https://doi.org/{doi}" if doi else url

        return f"{author_str} {year}, '{title}', {journal_info}, available at: {url_info}"

    # Fallback to original format
    if author and year:
        return f"{author} ({year}) '{title}', {source_name}, available at: {url}"
    else:
        return f"{source_name} (n.d.) '{title}', available at: {url}"
