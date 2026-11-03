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

def test_memory_requires_owner():
    assert client.post('/api/memory/clear').status_code == 401

def test_memory_clear_owner(monkeypatch):
    from app import HISTORY
    monkeypatch.setenv('JARVIS_OWNER_PASSWORD', 'test-owner-password')
    monkeypatch.setenv('JARVIS_LOCAL_DEV', '1')
    with TestClient(app) as owner:
        assert owner.post('/api/auth/login', json={'password': 'test-owner-password'}).status_code == 200
        token = owner.cookies.get('jarvis_session')
        from collections import deque
        HISTORY[token] = deque([{'role': 'user', 'content': 'temporary'}], maxlen=16)
        assert owner.post('/api/memory/clear').json() == {'cleared': True}
        assert token not in HISTORY
        assert owner.post('/api/auth/logout').status_code == 200

def test_task_requires_owner():
    assert client.get('/api/tasks').status_code == 401
    assert client.post('/api/tasks', json={'title': 'Draft report'}).status_code == 401

def test_task_workflow(monkeypatch):
    monkeypatch.setenv('JARVIS_OWNER_PASSWORD', 'test-owner-password')
    monkeypatch.setenv('JARVIS_LOCAL_DEV', '1')
    with TestClient(app) as owner:
        assert owner.post('/api/auth/login', json={'password': 'test-owner-password'}).status_code == 200
        created = owner.post('/api/tasks', json={'title': 'Draft report'})
        assert created.status_code == 201
        task_id = created.json()['id']
        assert created.json()['status'] == 'pending'
        assert owner.post(f'/api/tasks/{task_id}/action', json={'action': 'complete'}).status_code == 409
        approved = owner.post(f'/api/tasks/{task_id}/action', json={'action': 'approve'})
        assert approved.status_code == 200
        assert approved.json()['status'] == 'approved'
        done = owner.post(f'/api/tasks/{task_id}/action', json={'action': 'complete'})
        assert done.status_code == 200
        assert done.json()['status'] == 'completed'
        assert owner.delete('/api/tasks').json()['cleared'] == 1
        assert owner.post('/api/auth/logout').status_code == 200

def test_tasks_isolated_between_sessions(monkeypatch):
    monkeypatch.setenv('JARVIS_OWNER_PASSWORD', 'test-owner-password')
    monkeypatch.setenv('JARVIS_LOCAL_DEV', '1')
    with TestClient(app) as owner_a, TestClient(app) as owner_b:
        assert owner_a.post('/api/auth/login', json={'password':'test-owner-password'}).status_code == 200
        assert owner_b.post('/api/auth/login', json={'password':'test-owner-password'}).status_code == 200
        assert owner_a.post('/api/tasks', json={'title':'Only in session A'}).status_code == 201
        assert owner_b.get('/api/tasks').json()['tasks'] == []
        assert owner_a.post('/api/auth/logout').status_code == 200
        assert owner_b.post('/api/auth/logout').status_code == 200

def test_security_headers():
    response = client.get('/')
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-frame-options'] == 'DENY'
    assert "default-src 'self'" in response.headers['content-security-policy']
    assert response.headers['cache-control'] == 'no-store'

def test_cross_origin_login_blocked():
    response = client.post(
        '/api/auth/login',
        json={'password': 'anything'},
        headers={'origin': 'https://attacker.invalid'}
    )
    assert response.status_code == 403

def test_task_due_date_and_input_validation(monkeypatch):
    monkeypatch.setenv('JARVIS_OWNER_PASSWORD', 'test-owner-password')
    monkeypatch.setenv('JARVIS_LOCAL_DEV', '1')
    with TestClient(app) as owner:
        assert owner.post('/api/auth/login', json={'password':'test-owner-password'}).status_code == 200
        good = owner.post('/api/tasks', json={'title':'Prepare assignment', 'due_at':'2026-11-15T10:00:00+05:30'})
        assert good.status_code == 201
        assert good.json()['due_at'].startswith('2026-11-15T10:00:00')
        assert owner.post('/api/tasks', json={'title':'No timezone', 'due_at':'2026-11-15T10:00:00'}).status_code == 422
        assert owner.post('/api/tasks', json={'title':'   '}).status_code == 422
        assert owner.post('/api/auth/logout').status_code == 200

def test_ai_memory_round_trip_without_api_charges(monkeypatch):
    import importlib
    api = importlib.import_module('app')
    from collections import deque

    calls = []
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {'output': [{'content': [{'type': 'output_text', 'text': 'Acknowledged.'}]}]}

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, headers=None, json=None):
            assert url == 'https://api.openai.com/v1/responses'
            assert headers['Authorization'] == 'Bearer fake-test-key'
            calls.append(json)
            return FakeResponse()

    monkeypatch.setenv('JARVIS_OWNER_PASSWORD', 'test-owner-password')
    monkeypatch.setenv('JARVIS_LOCAL_DEV', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-test-key')
    monkeypatch.setattr(api.httpx, 'AsyncClient', FakeClient)

    with TestClient(app) as owner:
        assert owner.post('/api/auth/login', json={'password':'test-owner-password'}).status_code == 200
        assert owner.post('/api/chat', json={'message':'Remember blue'}).json()['mode'] == 'ai'
        assert owner.post('/api/chat', json={'message':'What color?'}).json()['answer'] == 'Acknowledged.'
        assert calls[0]['input'] == [{'role':'user','content':'Remember blue'}]
        assert len(calls[1]['input']) == 3
        assert calls[1]['input'][0]['content'] == 'Remember blue'
        assert calls[0]['store'] is False
        assert calls[0]['tool_choice'] == 'none'
        assert owner.post('/api/memory/clear').json()['cleared'] is True
        assert owner.post('/api/chat', json={'message':'Reset confirmed'}).status_code == 200
        assert len(calls[2]['input']) == 1
        owner.post('/api/auth/logout')

def test_system_diagnostics_are_owner_only(monkeypatch):
    assert client.get('/api/system/status').status_code == 401
    public = client.get('/api/health').json()
    assert 'ai_configured' not in public
    monkeypatch.setenv('JARVIS_OWNER_PASSWORD', 'test-owner-password')
    monkeypatch.setenv('JARVIS_LOCAL_DEV', '1')
    with TestClient(app) as owner:
        assert owner.post('/api/auth/login', json={'password': 'test-owner-password'}).status_code == 200
        status = owner.get('/api/system/status')
        assert status.status_code == 200
        data = status.json()
        assert data['task_execution_enabled'] is False
        assert data['persistent_storage_enabled'] is False
        assert isinstance(data['chat_requests_remaining'], int)
        owner.post('/api/auth/logout')
