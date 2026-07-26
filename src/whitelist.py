from __future__ import annotations

import json
import os
from urllib.parse import urlparse

# Load base whitelist
_whitelist_path = os.path.join(os.path.dirname(__file__), 'whitelist.json')
with open(_whitelist_path) as f:
    WHITELIST = json.load(f)

# Load packs if available
_packs_path = os.path.join(os.path.dirname(__file__), 'whitelist_packs.json')
WHITELIST_PACKS = {}
if os.path.exists(_packs_path):
    with open(_packs_path) as f:
        WHITELIST_PACKS = json.load(f)

KLA_TO_PACKS = {
    "Science": ["science"],
    "Mathematics": ["science"],
    "English": ["humanities"],
    "HSIE": ["humanities", "legal", "economics"],
    "Creative Arts": ["creative_arts"],
    "Languages": ["languages"],
    "TAS": ["science"],
    "PDHPE": ["science"],
}


def get_domains_for_kla(kla: str | None = None) -> list[str]:
    """Get merged domain/pattern list: base + KLA-specific packs."""
    domains = list(WHITELIST.get("domains", []))
    patterns = list(WHITELIST.get("domain_patterns", []))
    for pack_name in KLA_TO_PACKS.get(kla, []):
        pack = WHITELIST_PACKS.get(pack_name, {})
        for d in pack.get("domains", []):
            if d.startswith("*."):
                suffix = d[2:]
                if suffix not in [p[2:] for p in patterns if p.startswith("*.")]:
                    patterns.append(d)
            else:
                if d not in domains:
                    domains.append(d)
    return domains + patterns


def is_allowed(url: str, domains: list[str] | None = None) -> bool:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if parsed.scheme.lower() not in {"http", "https"} or not hostname:
            return False
        check_domains = domains if domains is not None else WHITELIST["domains"]
        check_patterns = []
        if domains is None:
            check_patterns = WHITELIST["domain_patterns"]
        else:
            for d in domains:
                if d.startswith("*."):
                    check_patterns.append(d)
        if hostname in check_domains:
            return True
        for pattern in check_patterns:
            if pattern.startswith('*.'):
                suffix = pattern[2:]
                if hostname.endswith('.' + suffix):
                    return True
        return False
    except Exception:
        return False


def get_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.hostname or ''
    except Exception:
        return ''


def get_whitelisted_domains(_kla: str | None = None) -> list[str]:
    """Return the explicitly whitelisted domains, optionally filtered by KLA."""
    return list(WHITELIST.get('domains', []))


def get_whitelisted_domain_patterns(_kla: str | None = None) -> list[str]:
    """Return approved wildcard domain patterns, optionally filtered by KLA."""
    return list(WHITELIST.get('domain_patterns', []))


def get_whitelist_search_scope(kla: str | None = None) -> str:
    """Generate a SerpAPI site scope covering base + KLA-specific domains."""
    domains = get_domains_for_kla(kla)
    scope_parts = []
    for entry in domains:
        if entry.startswith("*."):
            scope_parts.append(f"site:{entry}")
        else:
            scope_parts.append(f"site:{entry}")
    return " OR ".join(scope_parts) if scope_parts else ""


def get_display_name_for_domain(domain: str) -> str:
    domain_names = {
        'en.wikipedia.org': 'Wikipedia',
        'web.md': 'WebMD',
        'scholar.google.com': 'Google Scholar',
        'pubmed.ncbi.nlm.nih.gov': 'PubMed',
        'www.jstor.org': 'JSTOR',
        'eric.ed.gov': 'ERIC',
        'www.sciencedirect.com': 'ScienceDirect',
        'link.springer.com': 'Springer',
        'www.researchgate.net': 'ResearchGate',
        'www.academia.edu': 'Academia',
        'books.google.com': 'Google Books',
        'www.britannica.com': 'Britannica',
        'www.bbc.co.uk': 'BBC',
        'www.nationalgeographic.com': 'National Geographic',
    }
    if domain in domain_names:
        return domain_names[domain]
    if domain.startswith('*.'):
        return f"All {domain[2:]} sites"
    domain_clean = domain.replace('www.', '').replace('.com', '').replace('.org', '').replace('.net', '').replace('.edu', '')
    return domain_clean.title()
