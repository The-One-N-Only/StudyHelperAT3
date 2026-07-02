import requests
import os
from urllib.parse import quote
import json
import src.db as db
import src.whitelist as whitelist
from xml.etree import ElementTree as ET
from dotenv import load_dotenv

load_dotenv()

USER_AGENT = "StudyLib/1.0 (Academic Research Assistant)"
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "")
PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Default parameters for PubMed API
SEARCH_PARAMS = {
    "retmode": "json",
    "retmax": 100,
    "sort": "relevance"
}


def _build_search_query(query, mesh_terms=None, min_date=None, max_date=None):
    """Build a PubMed search query with optional filters."""
    search_parts = [query]

    if mesh_terms:
        mesh_query = " OR ".join([f'"{term}"[MeSH Terms]' for term in mesh_terms])
        search_parts.append(f"({mesh_query})")

    if min_date:
        search_parts.append(f'{min_date}[PDAT] : {max_date or "3000"}[PDAT]')

    return " AND ".join(search_parts) if len(search_parts) > 1 else query


def search(query, num_results=20, mesh_terms=None, min_date=None, max_date=None, *, user_id):
    """
    Search PubMed using ESearch.

    Args:
        query: Search terms
        num_results: Number of results to return (max 100)
        mesh_terms: List of MeSH terms to filter by
        min_date: Minimum publication date (YYYY/MM/DD or YYYY)
        max_date: Maximum publication date (YYYY/MM/DD or YYYY)
        user_id: User ID for database operations

    Returns:
        List of search result items
    """
    try:
        # Build the search query
        search_query = _build_search_query(query, mesh_terms, min_date, max_date)

        # ESearch endpoint
        params = {
            **SEARCH_PARAMS,
            "db": "pubmed",
            "term": search_query,
            "retmax": min(num_results, 100)
        }

        if PUBMED_API_KEY:
            params["api_key"] = PUBMED_API_KEY

        headers = {"User-Agent": USER_AGENT}

        esearch_url = f"{PUBMED_BASE_URL}/esearch.fcgi"
        resp = requests.get(esearch_url, params=params, headers=headers, timeout=10)

        if resp.status_code != 200:
            return []

        data = resp.json()
        pmids = data.get("esearchresult", {}).get("idlist", [])

        if not pmids:
            return []

        # Fetch detailed information for each PMID
        return _fetch_articles(pmids, user_id)

    except Exception as e:
        print(f"PubMed search error: {str(e)}")
        return []


def _fetch_articles(pmids, user_id):
    """
    Fetch detailed article information using EFetch.

    Args:
        pmids: List of PubMed IDs
        user_id: User ID for database operations

    Returns:
        List of article data dictionaries
    """
    if not pmids:
        return []

    try:
        # EFetch endpoint
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "medline"
        }

        if PUBMED_API_KEY:
            params["api_key"] = PUBMED_API_KEY

        headers = {"User-Agent": USER_AGENT}
        efetch_url = f"{PUBMED_BASE_URL}/efetch.fcgi"

        resp = requests.get(efetch_url, params=params, headers=headers, timeout=15)

        if resp.status_code != 200:
            return []

        # Parse XML response
        root = ET.fromstring(resp.content)
        articles = root.findall(".//PubmedArticle")

        results = []
        for article in articles:
            article_data = _parse_article(article)
            if article_data:
                # Create or get item from database
                item = db.get_item_by_source("pubmed", article_data["source_id"], user_id, True) or db.create_item(article_data, user_id, True)
                results.append(item)

        return results

    except Exception as e:
        print(f"PubMed fetch error: {str(e)}")
        return []


def _parse_article(article_elem):
    """
    Parse a PubmedArticle XML element into our item format.

    Returns:
        Dictionary with title, description, source_url, etc. or None
    """
    try:
        medlinecitation = article_elem.find("MedlineCitation")
        if medlinecitation is None:
            return None

        article = medlinecitation.find("Article")
        if article is None:
            return None

        # Extract PMID
        pmid_elem = medlinecitation.find("PMID")
        source_id = pmid_elem.text if pmid_elem is not None else None
        if not source_id:
            return None

        # Extract title
        title_elem = article.find("ArticleTitle")
        title = title_elem.text if title_elem is not None else "Untitled"

        # Extract authors
        authors = []
        author_list = article.find("AuthorList")
        if author_list is not None:
            for author in author_list.findall("Author"):
                last_name = author.find("LastName")
                first_name = author.find("ForeName")
                if last_name is not None:
                    author_name = last_name.text
                    if first_name is not None:
                        author_name += ", " + first_name.text
                    authors.append(author_name)

        # Extract abstract
        abstract_elem = article.find("Abstract")
        abstract = ""
        if abstract_elem is not None:
            abstract_parts = abstract_elem.findall("AbstractText")
            abstract = " ".join([p.text for p in abstract_parts if p.text])

        # Extract journal, year, volume, issue
        journal_info = article.find("Journal")
        journal = ""
        year = ""
        volume = ""
        issue = ""

        if journal_info is not None:
            journal_elem = journal_info.find("Title")
            journal = journal_elem.text if journal_elem is not None else ""

            pub_date_info = journal_info.find("JournalIssue")
            if pub_date_info is not None:
                volume_elem = pub_date_info.find("Volume")
                volume = volume_elem.text if volume_elem is not None else ""

                issue_elem = pub_date_info.find("Issue")
                issue = issue_elem.text if issue_elem is not None else ""

                # Extract year
                pub_date = pub_date_info.find("PubDate")
                if pub_date is not None:
                    year_elem = pub_date.find("Year")
                    year = year_elem.text if year_elem is not None else ""

        # Extract DOI and other IDs
        doi = None
        article_id_list = article.find("ArticleIdList")
        if article_id_list is not None:
            for article_id in article_id_list.findall("ArticleId"):
                id_type = article_id.get("IdType", "").lower()
                if id_type == "doi":
                    doi = article_id.text
                    break

        # Build source URL
        source_url = f"https://pubmed.ncbi.nlm.nih.gov/{source_id}/"

        # Build description
        description_parts = []
        if authors:
            description_parts.append(f"By {', '.join(authors[:3])}")
            if len(authors) > 3:
                description_parts.append(f"and {len(authors) - 3} others")

        if journal:
            journal_info_str = journal
            if year:
                journal_info_str += f" ({year})"
            if volume:
                journal_info_str += f"; {volume}"
            if issue:
                journal_info_str += f"({issue})"
            description_parts.append(journal_info_str)

        description = " • ".join(description_parts)

        # Build item data
        item_data = {
            "title": title,
            "description": description,
            "thumb_url": "",
            "thumb_mime": "image/jpeg",
            "thumb_height": 0,
            "source_url": source_url,
            "source_name": "pubmed",
            "source_id": source_id,
            "abstract": abstract,
            "authors": json.dumps(authors),
            "journal": journal,
            "year": year,
            "volume": volume,
            "issue": issue,
            "doi": doi
        }

        # Validate URL
        if item_data["source_url"] and whitelist.is_allowed(item_data["source_url"]):
            return item_data

        return None

    except Exception as e:
        print(f"Error parsing article: {str(e)}")
        return None


def get_related_articles(pmid, num_results=10, *, user_id):
    """
    Find articles related to a given PubMed ID using ELink.

    Args:
        pmid: PubMed ID
        num_results: Number of related articles to return
        user_id: User ID for database operations

    Returns:
        List of related article items
    """
    try:
        params = {
            "dbfrom": "pubmed",
            "db": "pubmed",
            "id": pmid,
            "retmax": min(num_results, 100),
            "retmode": "json"
        }

        if PUBMED_API_KEY:
            params["api_key"] = PUBMED_API_KEY

        headers = {"User-Agent": USER_AGENT}
        elink_url = f"{PUBMED_BASE_URL}/elink.fcgi"

        resp = requests.get(elink_url, params=params, headers=headers, timeout=10)

        if resp.status_code != 200:
            return []

        data = resp.json()
        linked_ids = []

        for linkset in data.get("linksets", []):
            for linksetdb in linkset.get("linksetdbs", []):
                linked_ids.extend(linksetdb.get("links", []))

        if not linked_ids:
            return []

        # Fetch details for related articles
        return _fetch_articles(linked_ids[:num_results], user_id)

    except Exception as e:
        print(f"PubMed related articles error: {str(e)}")
        return []


def get_mesh_terms(query, num_results=20):
    """
    Get suggested MeSH terms for a search query.

    Args:
        query: Search query
        num_results: Number of suggestions

    Returns:
        List of MeSH term suggestions
    """
    try:
        params = {
            "db": "mesh",
            "term": f"{query}[All Fields]",
            "retmax": num_results,
            "retmode": "json"
        }

        if PUBMED_API_KEY:
            params["api_key"] = PUBMED_API_KEY

        headers = {"User-Agent": USER_AGENT}
        esearch_url = f"{PUBMED_BASE_URL}/esearch.fcgi"

        resp = requests.get(esearch_url, params=params, headers=headers, timeout=10)

        if resp.status_code != 200:
            return []

        data = resp.json()
        return data.get("esearchresult", {}).get("idlist", [])

    except Exception as e:
        print(f"PubMed MeSH terms error: {str(e)}")
        return []
