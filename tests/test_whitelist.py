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