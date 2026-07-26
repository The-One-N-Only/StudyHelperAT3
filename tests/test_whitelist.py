import pytest

import src.whitelist as whitelist


def test_allowed_exact_domain():
    assert whitelist.is_allowed("https://en.wikipedia.org/wiki/Test")

def test_allowed_wildcard_domain():
    assert whitelist.is_allowed("https://uni.edu.au/page")

def test_not_allowed_domain():
    assert not whitelist.is_allowed("https://example.com/page")

def test_malformed_url():
    assert not whitelist.is_allowed("not-a-url")

def test_get_domain():
    assert whitelist.get_domain("https://en.wikipedia.org/wiki/Test") == "en.wikipedia.org"


def test_get_whitelisted_domains():
    domains = whitelist.get_whitelisted_domains()
    assert isinstance(domains, list)
    assert 'en.wikipedia.org' in domains
    assert 'pubmed.ncbi.nlm.nih.gov' in domains


def test_allowed_gov_wildcard_domain():
    assert whitelist.is_allowed("https://www.usa.gov/page")


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
