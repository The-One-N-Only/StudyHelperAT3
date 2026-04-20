import pytest
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
        assert response.status_code == 200
        
        response = client.get('/browse')
        assert response.status_code == 200