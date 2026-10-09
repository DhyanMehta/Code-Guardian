from unittest.mock import patch
from fastapi import HTTPException
from backend.db.models import Installation, UserInstallation
from backend.tests.conftest import _TestSessionLocal, create_test_auth_env, make_auth_cookies

def seed():
    with _TestSessionLocal() as db:
        user, first = create_test_auth_env(db)
        second = Installation(id=222, account_login="team", account_type="Organization", review_mode="manual")
        third = Installation(id=333, account_login="member-team", review_mode="manual")
        db.add_all([second, third]); db.flush()
        db.add_all([UserInstallation(user_id=user.id, installation_id=222, role="admin"), UserInstallation(user_id=user.id, installation_id=333, role="member")]); db.commit()
        return first.id

def test_atomic_shared_mode_and_stale_conflict(client):
    first = seed(); client.cookies.update(make_auth_cookies())
    snapshot = client.get('/profile/review-mode').json()
    assert snapshot['review_mode'] == 'mixed'
    assert {i['id'] for i in snapshot['installations']} == {first, 222}
    with patch('backend.api.profile.require_manager') as manager:
        response = client.patch('/profile/review-mode', json={'review_mode':'auto','version':snapshot['version']})
        assert response.status_code == 200
        assert manager.call_count == 2
        assert client.patch('/profile/review-mode', json={'review_mode':'manual','version':snapshot['version']}).status_code == 409
    with _TestSessionLocal() as db:
        assert db.get(Installation,222).review_mode == 'auto'
        assert db.get(Installation,333).review_mode == 'manual'

def test_failed_authorization_never_partially_applies(client):
    first = seed(); client.cookies.update(make_auth_cookies())
    snapshot = client.get('/profile/review-mode').json()
    with patch('backend.api.profile.require_manager', side_effect=[None, HTTPException(403,'denied')]):
        assert client.patch('/profile/review-mode', json={'review_mode':'manual','version':snapshot['version']}).status_code == 403
    with _TestSessionLocal() as db:
        assert db.get(Installation,first).review_mode == 'auto'

def test_profile_requires_session_and_installation_url_is_server_owned(client):
    assert client.get('/profile/review-mode').status_code == 401
    seed(); client.cookies.update(make_auth_cookies())
    response = client.get('/auth/installation-url')
    assert response.status_code == 200
    assert response.json()['url'].startswith('https://github.com/apps/')

def test_scope_change_requires_refresh(client):
    seed(); client.cookies.update(make_auth_cookies())
    snapshot=client.get('/profile/review-mode').json()
    with _TestSessionLocal() as db:
        link=db.query(UserInstallation).filter_by(installation_id=222).one()
        link.role='member'; db.commit()
    with patch('backend.api.profile.require_manager'):
        assert client.patch('/profile/review-mode',json={'review_mode':'manual','version':snapshot['version']}).status_code==409
