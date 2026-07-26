from __future__ import annotations

import json

KLA_CITATION_STYLES = {
    "Science": "apa",
    "Mathematics": "apa",
    "English": "mla",
    "HSIE": "chicago",
    "Creative Arts": "mla",
    "Languages": "apa",
    "TAS": "apa",
    "PDHPE": "apa",
}


def get_default_style_for_kla(kla: str) -> str:
    return KLA_CITATION_STYLES.get(kla, "apa")


def _parse_authors(authors_raw: str | list[str] | None) -> list[str] | None:
    if not authors_raw:
        return None
    try:
        return json.loads(authors_raw) if isinstance(authors_raw, str) else authors_raw
    except (json.JSONDecodeError, TypeError):
        return None


def _format_author_list_apa(author_list: list[str]) -> str:
    if len(author_list) > 20:
        return ", ".join(author_list[:20]) + ", et al."
    return ", ".join(author_list)


def _format_academic_citation(
    style: str,
    title: str,
    url: str,
    author_list: list[str] | None,
    journal: str | None,
    year: str | None,
    volume: str | None,
    issue: str | None,
    doi: str | None,
) -> str:
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


def _format_web_citation(
    style: str,
    title: str,
    source_name: str,
    url: str,
    author: str | None,
    year: str | None,
) -> str:
    if style == "harvard":
        if author and year:
            return f"{author} ({year}) '{title}', {source_name}, available at: {url}"
        return f"{source_name} (n.d.) '{title}', available at: {url}"
    else:
        if author and year:
            return f"{author}, A. ({year}). {title}. {source_name}. {url}"
        return f"{source_name}. (n.d.). {title}. Retrieved from {url}"


def format_apa(
    title: str,
    source_name: str,
    url: str,
    author: str | None = None,
    year: str | None = None,
    authors: str | None = None,
    journal: str | None = None,
    volume: str | None = None,
    issue: str | None = None,
    doi: str | None = None,
    _publisher: str | None = None,
    _pages: str | None = None,
) -> str:
    author_list = _parse_authors(authors)
    if author_list is not None and journal:
        return _format_academic_citation("apa", title, url, author_list, journal, year, volume, issue, doi)
    return _format_web_citation("apa", title, source_name, url, author, year)


def format_harvard(
    title: str,
    source_name: str,
    url: str,
    author: str | None = None,
    year: str | None = None,
    authors: str | None = None,
    journal: str | None = None,
    volume: str | None = None,
    issue: str | None = None,
    doi: str | None = None,
    _publisher: str | None = None,
    _pages: str | None = None,
) -> str:
    author_list = _parse_authors(authors)
    if author_list is not None and journal:
        return _format_academic_citation("harvard", title, url, author_list, journal, year, volume, issue, doi)
    return _format_web_citation("harvard", title, source_name, url, author, year)


def _format_author_last_first(author: str | None) -> str:
    if not author:
        return ""
    parts = author.strip().split(None, 1)
    if len(parts) == 1:
        return parts[0]
    return f"{parts[1]}, {parts[0]}"


def format_mla(
    title: str,
    source: str,
    url: str,
    author: str | None = None,
    year: str | None = None,
    publisher: str | None = None,
    pages: str | None = None,
    volume: str | None = None,
    issue: str | None = None,
    _doi: str | None = None,
) -> str:
    formatted_author = _format_author_last_first(author) + ". " if author else ""
    journal_part = ""
    if volume or issue:
        journal_part = ", vol. " + (volume or "") + ", no. " + (issue or "")
    pages_part = ""
    if pages:
        pages_part = ", pp. " + pages
    publisher_part = ""
    if publisher and not volume:
        publisher_part = ", " + publisher
    year_part = ", " + (year or "n.d.")
    return f'{formatted_author}"{title}." {source}{journal_part}{publisher_part}{pages_part}{year_part}, {url}.'


def format_chicago(
    title: str,
    source: str,
    url: str,
    author: str | None = None,
    year: str | None = None,
    publisher: str | None = None,
    pages: str | None = None,
    volume: str | None = None,
    issue: str | None = None,
    _doi: str | None = None,
) -> str:
    formatted_author = author.strip() + ". " if author else ""
    info_parts = [source]
    if volume:
        info_parts.append("vol. " + volume)
    if issue:
        info_parts.append("no. " + issue)
    if publisher:
        info_parts.append(publisher)
    if year:
        info_parts.append(year)
    info_str = ". ".join(info_parts)
    pages_str = ""
    if pages:
        pages_str = ", " + pages
    return f'{formatted_author}"{title}." {info_str}{pages_str}. {url}.'


def format_ieee(
    title: str,
    source: str,
    url: str,
    author: str | None = None,
    year: str | None = None,
    _publisher: str | None = None,
    _pages: str | None = None,
    _volume: str | None = None,
    _issue: str | None = None,
    _doi: str | None = None,
) -> str:
    formatted_author = author.strip() + ", " if author else ""
    year_part = ", " + (year or "n.d.")
    return f'{formatted_author}"{title}," {source}{year_part}, {url}.'


def format_citation(
    title: str,
    source: str,
    url: str,
    style: str,
    author: str | None = None,
    year: str | None = None,
    **kwargs,
) -> str:
    kwargs.setdefault("publisher", None)
    kwargs.setdefault("pages", None)
    kwargs.setdefault("volume", None)
    kwargs.setdefault("issue", None)
    kwargs.setdefault("doi", None)
    if style == "apa":
        return format_apa(title, source, url, author=author, year=year, **kwargs)
    elif style == "harvard":
        return format_harvard(title, source, url, author=author, year=year, **kwargs)
    elif style == "mla":
        return format_mla(title, source, url, author=author, year=year, **kwargs)
    elif style == "chicago":
        return format_chicago(title, source, url, author=author, year=year, **kwargs)
    elif style == "ieee":
        return format_ieee(title, source, url, author=author, year=year, **kwargs)
    else:
        return format_apa(title, source, url, author=author, year=year, **kwargs)


def sort_bibliography(citations: list[str], style: str = "apa") -> list[str]:
    if not citations:
        return []
    if style == "ieee":
        return citations
    def sort_key(citation: str) -> tuple:
        first_line = citation.split(".")[0].strip()
        first_line = first_line.lstrip('"')
        for prefix in ("A ", "An ", "The "):
            if first_line.startswith(prefix):
                first_line = first_line[len(prefix):]
        return first_line.lower()
    return sorted(citations, key=sort_key)
