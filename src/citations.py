import json


def _parse_authors(authors_raw):
    if not authors_raw:
        return None
    try:
        return json.loads(authors_raw) if isinstance(authors_raw, str) else authors_raw
    except (json.JSONDecodeError, TypeError):
        return None


def _format_author_list_apa(author_list):
    if len(author_list) > 20:
        return ", ".join(author_list[:20]) + ", et al."
    return ", ".join(author_list)


def _format_academic_citation(style, title, url, author_list, journal, year, volume, issue, doi):
    if not author_list:
        author_str = journal or ""
    elif style == "harvard":
        author_str = author_list[0] + " et al." if len(author_list) > 1 else author_list[0]
    else:
        author_str = _format_author_list_apa(author_list)

    journal_info = journal or ""
    if volume:
        journal_info += f", {volume}"
    if issue:
        journal_info += f"({issue})"

    if style == "harvard":
        url_part = f"https://doi.org/{doi}" if doi else url
        return f"{author_str} {year}, '{title}', {journal_info}, available at: {url_part}"
    else:
        citation = f"{author_str} ({year}). {title}. {journal_info}."
        if doi:
            citation += f" https://doi.org/{doi}"
        else:
            citation += f" Retrieved from {url}"
        return citation


def _format_web_citation(style, title, source_name, url, author, year):
    if style == "harvard":
        if author and year:
            return f"{author} ({year}) '{title}', {source_name}, available at: {url}"
        return f"{source_name} (n.d.) '{title}', available at: {url}"
    else:
        if author and year:
            return f"{author}, A. ({year}). {title}. {source_name}. {url}"
        return f"{source_name}. (n.d.). {title}. Retrieved from {url}"


def format_apa(title, source_name, url, author=None, year=None, authors=None, journal=None, volume=None, issue=None, doi=None):
    author_list = _parse_authors(authors)
    if author_list is not None and journal:
        return _format_academic_citation("apa", title, url, author_list, journal, year, volume, issue, doi)
    return _format_web_citation("apa", title, source_name, url, author, year)


def format_harvard(title, source_name, url, author=None, year=None, authors=None, journal=None, volume=None, issue=None, doi=None):
    author_list = _parse_authors(authors)
    if author_list is not None and journal:
        return _format_academic_citation("harvard", title, url, author_list, journal, year, volume, issue, doi)
    return _format_web_citation("harvard", title, source_name, url, author, year)
