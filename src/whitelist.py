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
        if not hostname:
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


def get_whitelist_search_scope() -> list[str]:
    scopes = []
    for domain in WHITELIST.get('domains', []):
        scopes.append(f"site:{domain}")
    for pattern in WHITELIST.get('domain_patterns', []):
        if pattern.startswith('*.'):
            scopes.append(f"site:{pattern[2:]}")
        else:
            scopes.append(f"site:{pattern}")
    return scopes