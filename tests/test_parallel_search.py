#!/usr/bin/env python3
"""
Test script for parallel multi-source search endpoint.
Demonstrates the /api/browse/search-all functionality.
"""

import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
import src.search as search
import src.pubmed as pubmed

load_dotenv()


def test_parallel_search():
    print("=" * 70)
    print("Testing Parallel Multi-Source Search")
    print("=" * 70)

    query = "machine learning"
    num_results = 10

    print(f"\nSearching for: '{query}'")
    print(f"Results per source: {num_results}")
    print(f"Sources: Wikipedia, Google Books, PubMed\n")

    import concurrent.futures

    search_tasks = {
        'wikipedia': (search.wikipedia, (query, num_results)),
        'gbooks': (search.gbooks, (query, num_results, {})),
        'pubmed': (pubmed.search, (query, num_results))
    }

    all_results = []
    source_counts = {}

    print("Starting parallel searches...")
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}

        for source in search_tasks:
            func, args = search_tasks[source]
            futures[source] = executor.submit(func, *args, user_id=1)
            print(f"  Submitted {source}")

        print("\nWaiting for results...\n")

        for source in futures:
            try:
                source_results = futures[source].result(timeout=15)
                all_results.extend(source_results or [])
                source_counts[source] = len(source_results) if source_results else 0
                print(f"  {source:12} - {source_counts[source]:2} results")
            except Exception as e:
                print(f"  {source:12} - FAILED: {str(e)}")
                source_counts[source] = 0

    end_time = time.time()

    print(f"\nTotal Results: {len(all_results)}")
    print(f"Total Time: {end_time - start_time:.2f} seconds")
    print(f"Source breakdown: {source_counts}\n")

    if all_results:
        print("Sample Results (first 5):\n")
        for i, result in enumerate(all_results[:5], 1):
            print(f"{i}. [{result.get('source_name', 'unknown').upper()}] {result.get('title', 'No title')}")
            if result.get('source_url'):
                print(f"   {result['source_url'][:70]}...")
            print()


def test_filtered_search():
    print("=" * 70)
    print("Testing Filtered Search (Only PubMed + Wikipedia)")
    print("=" * 70)

    query = "COVID-19"
    num_results = 5

    print(f"\nSearching for: '{query}'")
    print(f"Sources: PubMed, Wikipedia\n")

    import concurrent.futures

    search_tasks = {
        'wikipedia': (search.wikipedia, (query, num_results)),
        'pubmed': (pubmed.search, (query, num_results))
    }

    all_results = []
    source_counts = {}

    print("Starting parallel searches (subset of sources)...")
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}

        for source in search_tasks:
            func, args = search_tasks[source]
            futures[source] = executor.submit(func, *args, user_id=1)
            print(f"  Submitted {source}")

        print("\nWaiting for results...\n")

        for source in futures:
            try:
                source_results = futures[source].result(timeout=15)
                all_results.extend(source_results or [])
                source_counts[source] = len(source_results) if source_results else 0
                print(f"  {source:12} - {source_counts[source]:2} results")
            except Exception as e:
                print(f"  {source:12} - FAILED: {str(e)}")
                source_counts[source] = 0

    end_time = time.time()

    print(f"\nTotal Results: {len(all_results)}")
    print(f"Total Time: {end_time - start_time:.2f} seconds")
    print(f"Source breakdown: {source_counts}\n")


def test_client_filtering():
    print("=" * 70)
    print("Demonstrating Client-Side Result Filtering")
    print("=" * 70)

    mixed_results = [
        {'title': 'Article 1', 'source_name': 'wikipedia'},
        {'title': 'Article 2', 'source_name': 'pubmed'},
        {'title': 'Article 3', 'source_name': 'gbooks'},
        {'title': 'Article 4', 'source_name': 'pubmed'},
        {'title': 'Article 5', 'source_name': 'wikipedia'},
        {'title': 'Article 6', 'source_name': 'gbooks'},
    ]

    print("\nMixed Results (3 sources):")
    for r in mixed_results:
        print(f"  - {r['title']:15} from {r['source_name']}")

    print("\nClient-side filtering examples:\n")

    pubmed_only = [r for r in mixed_results if r['source_name'] == 'pubmed']
    print(f"Filter: Only PubMed results")
    print(f"  Result: {len(pubmed_only)} items - {[r['title'] for r in pubmed_only]}")

    academic = [r for r in mixed_results if r['source_name'] in ['pubmed', 'gbooks']]
    print(f"\nFilter: Only academic sources (PubMed + Books)")
    print(f"  Result: {len(academic)} items - {[r['title'] for r in academic]}")

    wikipedia_only = [r for r in mixed_results if r['source_name'] == 'wikipedia']
    print(f"\nFilter: Only Wikipedia results")
    print(f"  Result: {len(wikipedia_only)} items - {[r['title'] for r in wikipedia_only]}")

    print()


def main():
    print("\n" + "=" * 70)
    print("PARALLEL MULTI-SOURCE SEARCH TESTS")
    print("=" * 70 + "\n")

    test_parallel_search()
    print("\n")

    test_filtered_search()
    print("\n")

    test_client_filtering()

    print("=" * 70)
    print("All demonstrations complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
