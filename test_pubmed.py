#!/usr/bin/env python3
"""
Test script for PubMed E-utilities integration.
Run this to verify the PubMed search functionality is working correctly.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import pubmed, citations
from dotenv import load_dotenv

load_dotenv()


def test_pubmed_search():
    print("=" * 60)
    print("Testing PubMed Basic Search")
    print("=" * 60)

    query = "machine learning medical imaging"
    print(f"\nSearching for: {query}")
    print(f"API Key configured: {'Yes' if os.getenv('PUBMED_API_KEY') else 'No'}")

    try:
        results = pubmed.search(query, num_results=5, user_id=1)
        print(f"\nSearch successful! Found {len(results)} results")

        if results:
            result = results[0]
            print(f"\nFirst result:")
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  Authors: {result.get('authors', 'N/A')}")
            print(f"  Journal: {result.get('journal', 'N/A')}")
            print(f"  Year: {result.get('year', 'N/A')}")
            print(f"  PMID: {result.get('source_id', 'N/A')}")
            if result.get('abstract'):
                print(f"  Abstract: {result['abstract'][:200]}...")
    except Exception as e:
        print(f"Search failed: {str(e)}")
        import traceback
        traceback.print_exc()


def test_mesh_filtering():
    print("\n" + "=" * 60)
    print("Testing PubMed with MeSH Filtering")
    print("=" * 60)

    query = "cancer treatment"
    mesh_terms = ["Neoplasms", "Immunotherapy"]
    print(f"\nSearching for: {query}")
    print(f"MeSH terms: {mesh_terms}")

    try:
        results = pubmed.search(query, num_results=3, mesh_terms=mesh_terms, user_id=1)
        print(f"Search with MeSH filter successful! Found {len(results)} results")
    except Exception as e:
        print(f"Search failed: {str(e)}")


def test_date_filtering():
    print("\n" + "=" * 60)
    print("Testing PubMed with Date Filtering")
    print("=" * 60)

    query = "artificial intelligence"
    print(f"\nSearching for: {query}")
    print(f"Date range: 2023-2024")

    try:
        results = pubmed.search(query, num_results=3, min_date="2023", max_date="2024/12/31", user_id=1)
        print(f"Search with date filter successful! Found {len(results)} results")

        if results:
            for r in results:
                print(f"  - {r.get('title', 'N/A')} ({r.get('year', 'N/A')})")
    except Exception as e:
        print(f"Search failed: {str(e)}")


def test_mesh_suggestions():
    print("\n" + "=" * 60)
    print("Testing MeSH Term Suggestions")
    print("=" * 60)

    query = "cancer"
    print(f"\nGetting MeSH suggestions for: {query}")

    try:
        suggestions = pubmed.get_mesh_terms(query, num_results=5)
        print(f"Got {len(suggestions)} suggestions:")
        for term in suggestions[:5]:
            print(f"  - {term}")
    except Exception as e:
        print(f"Failed: {str(e)}")


def test_citation_formatting():
    print("\n" + "=" * 60)
    print("Testing Citation Formatting")
    print("=" * 60)

    article = {
        "title": "Deep Learning for Medical Image Analysis",
        "source_name": "pubmed",
        "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "authors": '["Smith, J", "Johnson, A", "Williams, B"]',
        "journal": "Journal of Medical AI",
        "year": "2023",
        "volume": "15",
        "issue": "3",
        "doi": "10.1234/jmai.2023.456"
    }

    print("\nSample article data:")
    print(f"  Title: {article['title']}")
    print(f"  Authors: {article['authors']}")
    print(f"  Journal: {article['journal']} ({article['year']})")

    try:
        apa = citations.format_apa(**article)
        harvard = citations.format_harvard(**article)

        print("\nCitation formatting successful!")
        print(f"\nAPA Format:\n{apa}")
        print(f"\nHarvard Format:\n{harvard}")
    except Exception as e:
        print(f"Citation formatting failed: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    print("\n" + "=" * 60)
    print("PubMed E-utilities Integration Tests")
    print("=" * 60)

    api_key = os.getenv("PUBMED_API_KEY")
    if api_key:
        print(f"\nPUBMED_API_KEY configured (first 10 chars: {api_key[:10]}...)")
    else:
        print("\nWARNING PUBMED_API_KEY not configured - using standard rate limits (3 req/sec)")

    test_pubmed_search()
    test_mesh_filtering()
    test_date_filtering()
    test_mesh_suggestions()
    test_citation_formatting()

    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
