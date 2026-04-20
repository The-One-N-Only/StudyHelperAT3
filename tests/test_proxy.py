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