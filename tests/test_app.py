from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_home():
    response = client.get('/')
    assert response.status_code == 200
    assert 'J.A.R.V.I.S.' in response.text

def test_health():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['ok'] is True

def test_local_chat(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    response = client.post('/api/chat', json={'message': 'hello jarvis'})
    assert response.status_code == 200
    assert response.json()['mode'] == 'local'

def test_empty_input_rejected():
    assert client.post('/api/chat', json={'message': ''}).status_code == 422

def test_long_input_rejected():
    assert client.post('/api/chat', json={'message': 'a' * 2001}).status_code == 422
