from unittest.mock import patch
from backend.db.models import Installation, UserInstallation
from backend.tests.conftest import _TestSessionLocal, create_test_auth_env, make_auth_cookies


def seed(client):
    with _TestSessionLocal() as db:
        create_test_auth_env(db)
    client.cookies.update(make_auth_cookies())


def test_refresh_reconciles_access_without_new_session_and_preserves_policy(client):
    seed(client)
    with _TestSessionLocal() as db:
        db.get(Installation, 123456).review_mode = 'manual'
        db.commit()
    payload = {'total_count': 1, 'installations': [{'id': 123456, 'account': {'login': 'owner', 'type': 'User'}, 'suspended_at': '2026-10-09T00:00:00Z'}]}
    with patch('backend.services.authorization.github_json', return_value=payload), patch('backend.api.auth.is_manager', return_value=False):
        response = client.post('/auth/installations/refresh?installation_id=999')
    assert response.status_code == 200
    assert 'session_jwt' not in response.cookies
    assert response.json()['installations'][0]['suspended'] is True
    assert response.json()['installations'][0]['role'] == 'member'
    with _TestSessionLocal() as db:
        assert db.get(Installation, 123456).review_mode == 'manual'
        assert db.get(Installation, 999) is None


def test_incomplete_pagination_preserves_existing_access(client):
    seed(client)
    with patch('backend.services.authorization.github_json', return_value={'total_count': 1, 'installations': []}):
        assert client.post('/auth/installations/refresh').status_code == 502
    with _TestSessionLocal() as db:
        assert db.query(UserInstallation).count() == 1


def test_empty_complete_list_removes_stale_access(client):
    seed(client)
    with patch('backend.services.authorization.github_json', return_value={'total_count': 0, 'installations': []}):
        response = client.post('/auth/installations/refresh')
    assert response.status_code == 200
    assert response.json()['installations'] == []


def test_refresh_requires_session(client):
    assert client.post('/auth/installations/refresh').status_code == 401
