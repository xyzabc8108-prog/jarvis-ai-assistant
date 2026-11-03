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
    assert response.status_code == 401

def test_empty_input_rejected():
    assert client.post('/api/chat', json={'message': ''}).status_code == 401

def test_long_input_rejected():
    assert client.post('/api/chat', json={'message': 'a' * 2001}).status_code == 401

def test_owner_login_and_chat(monkeypatch):
    monkeypatch.setenv('JARVIS_OWNER_PASSWORD', 'test-owner-password')
    monkeypatch.setenv('JARVIS_LOCAL_DEV', '1')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with TestClient(app) as owner:
        bad = owner.post('/api/auth/login', json={'password': 'wrong'})
        assert bad.status_code == 401
        good = owner.post('/api/auth/login', json={'password': 'test-owner-password'})
        assert good.status_code == 200
        response = owner.post('/api/chat', json={'message': 'hello jarvis'})
        assert response.status_code == 200
        assert response.json()['mode'] == 'local'
        owner.post('/api/auth/logout')
        assert owner.post('/api/chat', json={'message': 'hi'}).status_code == 401

def test_chat_hourly_limit(monkeypatch):
    monkeypatch.setenv('JARVIS_OWNER_PASSWORD', 'test-owner-password')
    monkeypatch.setenv('JARVIS_LOCAL_DEV', '1')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with TestClient(app) as owner:
        assert owner.post('/api/auth/login', json={'password': 'test-owner-password'}).status_code == 200
        results = [owner.post('/api/chat', json={'message': 'hi'}).status_code for _ in range(31)]
        assert results[:30] == [200] * 30
        assert results[30] == 429
        assert owner.post('/api/auth/logout').status_code == 200
