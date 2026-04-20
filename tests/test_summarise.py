import pytest
from unittest.mock import patch, Mock
import src.summarise as summarise

@patch('src.summarise.requests.post')
def test_summarise_url_success(mock_post):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": [{"text": '{"summary": "Test summary", "bullets": ["Bullet 1"], "relevance": "Relevant"}'}]
    }
    mock_post.return_value = mock_response
    
    with patch('src.proxy.fetch_source') as mock_fetch:
        mock_fetch.return_value = {"status": True, "text": "Long enough content"}
        
        result = summarise.summarise_url("https://example.com", "Title")
        assert result["status"] == True
        assert result["summary"] == "Test summary"

@patch('src.summarise.requests.post')
def test_summarise_url_short_content(mock_post):
    with patch('src.proxy.fetch_source') as mock_fetch:
        mock_fetch.return_value = {"status": True, "text": "Short"}
        
        result = summarise.summarise_url("https://example.com", "Title")
        assert result["status"] == False
        assert "insufficient" in result["error"]

@patch('src.summarise.requests.post')
def test_summarise_url_timeout(mock_post):
    mock_post.side_effect = Exception("Timeout")
    
    with patch('src.proxy.fetch_source') as mock_fetch:
        mock_fetch.return_value = {"status": True, "text": "Long enough content"}
        
        result = summarise.summarise_url("https://example.com", "Title")
        assert result["status"] == False
        assert "error" in result