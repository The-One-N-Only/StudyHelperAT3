import pytest
import app as app_module
from app import app
import json

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_full_workflow(client):
    # Mock external calls
    with client.application.app_context():
        # This would require setting up test DB and mocking all external APIs
        # For brevity, just check route exists
        response = client.get('/')
        assert response.status_code == 302
        
        response = client.get('/browse')
    assert response.status_code == 302


def test_google_books_config_endpoint_returns_key(client, monkeypatch):
    with client.session_transaction() as sess:
        sess['user_id'] = 1

    monkeypatch.setenv('GOOGLE_BOOKS_API_KEY', 'test-google-books-key')
    response = client.get('/api/config/google-books-key')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] is True
    assert data['google_books_api_key'] == 'test-google-books-key'


def test_browse_search_all_returns_grouped_results(client, monkeypatch):
    with client.session_transaction() as sess:
        sess['user_id'] = 1

    def fake_wikipedia(query, num_results, *, user_id):
        return [{
            'title': 'Wiki result',
            'description': 'Wikipedia test',
            'thumb_url': '',
            'thumb_mime': 'image/jpeg',
            'thumb_height': 0,
            'source_url': 'https://en.wikipedia.org/wiki/Test',
            'source_name': 'Wikipedia',
            'source_id': 'https://en.wikipedia.org/wiki/Test'
        }]

    def fake_pubmed(query, num_results, mesh_terms, min_date, max_date, *, user_id):
        return [{
            'title': 'PubMed result',
            'description': 'PubMed test',
            'thumb_url': '',
            'thumb_mime': 'image/jpeg',
            'thumb_height': 0,
            'source_url': 'https://pubmed.ncbi.nlm.nih.gov/test',
            'source_name': 'PubMed',
            'source_id': 'https://pubmed.ncbi.nlm.nih.gov/test'
        }]

    monkeypatch.setattr(app_module.search, 'wikipedia', fake_wikipedia)
    monkeypatch.setattr(app_module.pubmed, 'search', fake_pubmed)

    response = client.post('/api/browse/search-all', json={
        'query': 'test',
        'sources': ['wikipedia', 'pubmed'],
        'num_results': 10,
        'filters': {}
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] is True
    assert 'grouped_results' in data
    assert data['source_counts']['wikipedia'] == 1
    assert data['source_counts']['pubmed'] == 1
    assert len(data['results']) == 2
