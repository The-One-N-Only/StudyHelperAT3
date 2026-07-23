import pytest
import src.whitelist as whitelist

def test_allowed_exact_domain():
    assert whitelist.is_allowed("https://en.wikipedia.org/wiki/Test") == True

def test_allowed_wildcard_domain():
    assert whitelist.is_allowed("https://uni.edu.au/page") == True

def test_not_allowed_domain():
    assert whitelist.is_allowed("https://example.com/page") == False

def test_malformed_url():
    assert whitelist.is_allowed("not-a-url") == False

def test_get_domain():
    assert whitelist.get_domain("https://en.wikipedia.org/wiki/Test") == "en.wikipedia.org"


def test_get_whitelisted_domains():
    domains = whitelist.get_whitelisted_domains()
    assert isinstance(domains, list)
    assert 'en.wikipedia.org' in domains
    assert 'pubmed.ncbi.nlm.nih.gov' in domains


def test_get_domain_patterns():
    patterns = whitelist.get_whitelisted_domain_patterns()
    assert isinstance(patterns, list)
    assert "*.edu.au" in patterns
    assert "*.gov" in patterns

def test_get_whitelist_search_scope():
    scope = whitelist.get_whitelist_search_scope()
    assert "site:en.wikipedia.org" in scope
    assert "site:pubmed.ncbi.nlm.nih.gov" in scope
    assert "site:*.edu" in scope

@pytest.mark.parametrize("domain,expected", [
    ("en.wikipedia.org", "Wikipedia"),
    ("pubmed.ncbi.nlm.nih.gov", "PubMed"),
    ("books.google.com", "Google Books"),
    ("www.britannica.com", "Britannica"),
    ("www.sciencedirect.com", "ScienceDirect"),
    ("*.edu.au", "All edu.au sites"),
    ("unknown.example.com", "Unknown.Example"),
])
def test_get_display_name_for_domain(domain, expected):
    assert whitelist.get_display_name_for_domain(domain) == expected

def test_allowed_gov_wildcard_domain():
    assert whitelist.is_allowed("https://www.usa.gov/page") == True


@pytest.mark.parametrize(
    "url",
    (
        "javascript://en.wikipedia.org/alert(1)",
        "ftp://en.wikipedia.org/archive",
        "file://en.wikipedia.org/etc/passwd",
        "ws://en.wikipedia.org/socket",
    ),
)
def test_allowed_domain_rejects_non_http_schemes(url):
    assert whitelist.is_allowed(url) is False
