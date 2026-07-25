#!/usr/bin/env python3
"""Test script for PubMed E-utilities integration."""

import pytest
from dotenv import load_dotenv


@pytest.fixture(autouse=True)
def load_env():
    load_dotenv()


def test_pubmed_search():
    query = "machine learning medical imaging"
    from src import pubmed
    results = pubmed.search(query, num_results=5, user_id=1)
    assert len(results) > 0
    result = results[0]
    assert result.get('title')
    assert result.get('source_id')


def test_mesh_filtering():
    query = "cancer treatment"
    mesh_terms = ["Neoplasms", "Immunotherapy"]
    from src import pubmed
    results = pubmed.search(query, num_results=3, mesh_terms=mesh_terms, user_id=1)
    assert len(results) > 0


def test_date_filtering():
    query = "artificial intelligence"
    from src import pubmed
    results = pubmed.search(query, num_results=3, min_date="2023", max_date="2024/12/31", user_id=1)
    assert len(results) > 0
    for r in results:
        assert r.get('year')


def test_mesh_suggestions():
    query = "cancer"
    from src import pubmed
    suggestions = pubmed.get_mesh_terms(query, num_results=5)
    assert len(suggestions) > 0


def test_citation_formatting():
    from src import citations
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
    apa = citations.format_apa(**article)
    harvard = citations.format_harvard(**article)
    assert apa
    assert harvard
