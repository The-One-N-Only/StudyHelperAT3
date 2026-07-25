def search_openstax(query: str, limit: int = 5) -> list[dict]:
    OPENSTAX_BOOKS = {
        "Algebra and Trigonometry": {"url": "https://openstax.org/details/books/algebra-and-trigonometry-2e", "subjects": ["math"]},
        "Calculus Volume 1": {"url": "https://openstax.org/details/books/calculus-volume-1", "subjects": ["math"]},
        "Physics": {"url": "https://openstax.org/details/books/college-physics-2e", "subjects": ["physics", "science"]},
        "Biology 2e": {"url": "https://openstax.org/details/books/biology-2e", "subjects": ["biology", "science"]},
        "Chemistry 2e": {"url": "https://openstax.org/details/books/chemistry-2e", "subjects": ["chemistry", "science"]},
        "Psychology 2e": {"url": "https://openstax.org/details/books/psychology-2e", "subjects": ["psychology"]},
        "Sociology 2e": {"url": "https://openstax.org/details/books/sociology-2e", "subjects": ["sociology"]},
        "Economics": {"url": "https://openstax.org/details/books/economics-2e", "subjects": ["economics", "business"]},
        "US History": {"url": "https://openstax.org/details/books/us-history", "subjects": ["history"]},
    }
    query_lower = query.lower()
    results = []
    for name, info in OPENSTAX_BOOKS.items():
        if query_lower in name.lower() or any(s in query_lower for s in info["subjects"]):
            results.append({
                "source_name": "OpenStax",
                "title": name,
                "source_url": info["url"],
                "snippet": f"Free, peer-reviewed textbook on {', '.join(info['subjects'])}",
                "free": True,
            })
    return results[:limit]
