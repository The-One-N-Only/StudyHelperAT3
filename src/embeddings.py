import math
import hashlib
from typing import List

def _hash_feature(text: str, feature: str, dim: int) -> int:
    h = hashlib.md5(f"{text}:{feature}".encode()).hexdigest()
    return int(h, 16) % dim

def compute_simple_embedding(text: str, dim: int = 128) -> List[float]:
    if not text:
        return [0.0] * dim

    vector = [0.0] * dim

    text_lower = text.lower()
    for n in [2, 3, 4]:
        for i in range(len(text_lower) - n + 1):
            gram = text_lower[i:i+n]
            idx = _hash_feature(text, gram, dim)
            vector[idx] += 1.0

    magnitude = math.sqrt(sum(v*v for v in vector))
    if magnitude > 0:
        vector = [v / magnitude for v in vector]

    return vector

def cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x*x for x in a))
    mag_b = math.sqrt(sum(y*y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
