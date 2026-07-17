import pytest
from unittest.mock import patch, Mock
import src.proxy as proxy

@patch('src.proxy.requests.get')
def test_proxy_allowed_url(mock_get):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"<html><body>Test content</body></html>"
    mock_get.return_value = mock_response
    
    result = proxy.fetch_source("https://en.wikipedia.org/test")
    assert result["status"] == True
    assert "Test content" in result["html"]
    assert result["mode"] == "iframe"

@patch('src.proxy.requests.get')
def test_proxy_reader_mode_for_nhs(mock_get):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"<html><head><title>NHS</title></head><body><div>Patient info</div></body></html>"
    mock_get.return_value = mock_response

    result = proxy.fetch_source("https://www.nhs.uk/article")
    assert result["status"] == True
    assert result["mode"] == "reader"
    assert "Patient info" in result["html"]

@patch('src.proxy.requests.get')
def test_proxy_google_books_uses_native_viewer_without_remote_fetch(mock_get):
    source_url = "https://books.google.com/books?id=test"

    result = proxy.fetch_source(source_url)

    mock_get.assert_not_called()
    assert result["status"] is False
    assert "html" not in result
    assert result["fallback_url"] == source_url
    assert "native viewer" in result["error"].lower()

@patch('src.proxy.requests.get')
def test_proxy_not_allowed(mock_get):
    with pytest.raises(ValueError):
        proxy.fetch_source("https://example.com/test")

@patch('src.proxy.requests.get')
def test_proxy_non_200(mock_get):
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response
    
    result = proxy.fetch_source("https://en.wikipedia.org/test")
    assert result["status"] == False
    assert "Failed to load source" in result["error"]
