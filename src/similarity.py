import re


def _shingle(text: str, n: int = 5) -> set:
    """Create character n-gram shingles from text."""
    text = re.sub(r'\s+', ' ', text.lower()).strip()
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def _jaccard_similarity(a: set, b: set) -> float:
    intersection = a & b
    union = a | b
    if not union:
        return 0.0
    return len(intersection) / len(union)


def check_similarity(draft: str, source_texts: list[tuple[str, str, str]]) -> list[dict]:
    """
    Check draft text against source texts.
    source_texts: list of (source_title, source_url, source_text)
    Returns list of flagged passages with source attribution.
    """
    draft_shingles = _shingle(draft, n=8)
    results = []

    for title, url, text in source_texts:
        source_shingles = _shingle(text, n=8)
        similarity = _jaccard_similarity(draft_shingles, source_shingles)

        if similarity > 0.3:
            common = draft_shingles & source_shingles
            flagged_passages = _find_common_passages(draft, text, common)
            results.append({
                "source_title": title,
                "source_url": url,
                "similarity": round(similarity, 3),
                "flagged_passages": flagged_passages[:3],
            })

    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results


def _find_common_passages(draft: str, source: str, common_shingles: set) -> list[dict]:
    """Find overlapping text passages between draft and source."""
    sentences = re.split(r'(?<=[.!?])\s+', draft)
    passages = []
    for sent in sentences:
        sent_shingles = _shingle(sent, n=8)
        overlap = sent_shingles & common_shingles
        if len(overlap) > 2:
            source_sents = re.split(r'(?<=[.!?])\s+', source)
            best_match = max(source_sents, key=lambda s: _jaccard_similarity(
                _shingle(s, n=8), sent_shingles
            ), default="")
            passages.append({
                "draft_excerpt": sent[:200],
                "source_excerpt": best_match[:200],
            })
    return passages
