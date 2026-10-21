from unittest.mock import patch
import pytest
from fastapi import HTTPException
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


def test_refresh_rolls_back_when_later_manager_check_fails(client):
    seed(client)
    items = [{'id': 123456, 'account': {'login': 'changed', 'type': 'User'}},
             {'id': 222, 'account': {'login': 'team', 'type': 'Organization'}}]
    with patch('backend.services.authorization.github_json', return_value={'total_count': 2, 'installations': items}), patch('backend.api.auth.is_manager', side_effect=[True, HTTPException(403, 'Denied')]):
        assert client.post('/auth/installations/refresh').status_code == 403
    with _TestSessionLocal() as db:
        assert db.get(Installation, 123456).account_login != 'changed'
        assert db.get(Installation, 222) is None
        assert db.query(UserInstallation).count() == 1


@pytest.mark.parametrize('suspension', [123, {}, 'not-a-timestamp'])
def test_malformed_suspension_is_a_handled_upstream_error(client, suspension):
    seed(client)
    item = {'id': 123456, 'account': {'login': 'changed', 'type': 'User'}, 'suspended_at': suspension}
    with patch('backend.services.authorization.github_json', return_value={'total_count': 1, 'installations': [item]}):
        assert client.post('/auth/installations/refresh').status_code == 502
    with _TestSessionLocal() as db:
        assert db.get(Installation, 123456).account_login != 'changed'


def test_refresh_collects_all_pages_before_removing_old_access(client):
    seed(client)
    pages = [{'total_count': 2, 'installations': [{'id': i, 'account': {'login': 'owner', 'type': 'User'}}]} for i in [222, 333]]
    with patch('backend.services.authorization.github_json', side_effect=pages) as github, patch('backend.api.auth.is_manager', return_value=True):
        response = client.post('/auth/installations/refresh')
    assert response.status_code == 200
    assert {i['id'] for i in response.json()['installations']} == {222, 333}
    assert github.call_args.kwargs['params']['page'] == 2
