import json
import os
from urllib.parse import urlparse

# Load whitelist on import
with open(os.path.join(os.path.dirname(__file__), 'whitelist.json'), 'r') as f:
    WHITELIST = json.load(f)

def is_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if parsed.scheme.lower() not in {"http", "https"} or not hostname:
            return False
        # Check exact domains
        if hostname in WHITELIST['domains']:
            return True
        # Check patterns
        for pattern in WHITELIST['domain_patterns']:
            if pattern.startswith('*.'):
                suffix = pattern[2:]
                if hostname.endswith('.' + suffix):
                    return True
        return False
    except:
        return False

def get_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.hostname or ''
    except:
        return ''

def get_whitelisted_domains() -> list[str]:
    """Return the explicitly whitelisted domains from the whitelist configuration."""
    return list(WHITELIST.get('domains', []))

def get_whitelist_search_scope() -> str:
    """Generate a search scope string for Google Custom Search API using whitelisted domains."""
    scope_parts = []
    
    # Add exact domains
    for domain in WHITELIST.get('domains', []):
        scope_parts.append(f"site:{domain}")
    
    # Add wildcard patterns (converting *.edu to *.edu pattern)
    for pattern in WHITELIST.get('domain_patterns', []):
        if pattern.startswith('*.'):
            # For patterns like *.edu, use site pattern for Google Custom Search
            scope_parts.append(f"site:{pattern}")
    
    return " OR ".join(scope_parts) if scope_parts else ""

def get_display_name_for_domain(domain: str) -> str:
    """Get a user-friendly display name for a domain."""
    # Domain name mapping for nicer display
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
    
    # For unknown domains, clean up the domain name
    domain_clean = domain.replace('www.', '').replace('.com', '').replace('.org', '').replace('.net', '').replace('.edu', '')
    return domain_clean.title()
