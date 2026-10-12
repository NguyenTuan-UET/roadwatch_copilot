"""Accounts use a temporary store; sessions protect HTTP and WebRTC signaling."""
import sqlite3

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.roadwatch import web
from src.roadwatch.authstore import AuthStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(web, 'ACCOUNTS_ENABLED', True)
    monkeypatch.setattr(web, 'ACCOUNTS', AuthStore(tmp_path / 'accounts.db'))
    monkeypatch.setattr(web, 'COOKIE_SECURE', True)
    return TestClient(web.app, base_url='https://testserver')


def test_register_login_logout_and_protected_routes(client):
    assert client.get('/app', follow_redirects=False).status_code == 303
    assert client.get('/login').status_code == 200
    assert client.get('/api/rtc').status_code == 401
    assert 'www-authenticate' not in client.get('/api/rtc').headers
    credentials = {'username': 'new-driver', 'password': 'long-password'}
    response = client.post('/api/auth/register', json=credentials)
    assert response.status_code == 201 and response.json()['role'] == 'driver'
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=lax' in cookie
    assert client.get('/app').status_code == 200
    assert client.get('/api/auth/me').json()['username'] == 'new-driver'
    assert client.get('/api/rtc').status_code == 200
    assert client.get('/engineer').status_code == 403
    assert client.get('/api/lab/segments').status_code == 403
    with client.websocket_connect('/api/ws', headers={'Cookie': f'{web.SESSION_COOKIE}={client.cookies.get(web.SESSION_COOKIE)}', 'Origin': 'https://testserver'}) as socket:
        assert 'state' in socket.receive_json()
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/rtc').status_code == 401
    assert client.post('/api/auth/login', json=credentials | {'password': 'wrong-password'}).status_code == 401
    assert client.post('/api/auth/login', json=credentials).status_code == 200


def test_registration_cannot_grant_engineer_and_rejects_duplicates(client):
    credentials = {'username': 'driver', 'password': 'long-password'}
    assert client.post('/api/auth/register', json=credentials | {'role': 'engineer'}).status_code == 422
    assert client.post('/api/auth/register', json=credentials).status_code == 201
    assert client.post('/api/auth/register', json=credentials).status_code == 409
    assert client.post('/api/auth/register', json=credentials | {'password': 'short'}).status_code == 422


def test_foreign_origin_cannot_change_authenticated_state(client):
    response = client.post('/api/auth/register', json={'username': 'driver', 'password': 'long-password'},
                           headers={'Origin': 'https://attacker.invalid'})
    assert response.status_code == 403
    assert client.post('/api/auth/login', json={'username': 'driver', 'password': 'long-password'},
                       headers={'Origin': 'http://[invalid'}).status_code == 403
    client.post('/api/auth/register', json={'username': 'driver', 'password': 'long-password'})
    assert client.post('/api/stop', headers={'Origin': 'https://attacker.invalid'}).status_code == 403
    with pytest.raises(WebSocketDisconnect), client.websocket_connect('/api/ws', headers={'Origin': 'https://attacker.invalid', 'Cookie': f'{web.SESSION_COOKIE}={client.cookies.get(web.SESSION_COOKIE)}'}):
        pass


def test_revoked_cookie_and_basic_credentials_cannot_bypass_login(client, monkeypatch):
    monkeypatch.setattr(web, 'PASSWORD', 'engineer-password')
    client.auth = (web.USER, 'engineer-password')
    assert client.get('/api/status').status_code == 401
    client.post('/api/auth/register', json={'username': 'driver', 'password': 'long-password'})
    cookie = client.cookies.get(web.SESSION_COOKIE)
    client.post('/api/auth/logout')
    client.cookies.set(web.SESSION_COOKIE, cookie)
    assert client.get('/api/status').status_code == 401
    with pytest.raises(WebSocketDisconnect), client.websocket_connect('/api/ws'):
        pass


def test_store_hashes_passwords_revokes_tokens_and_expires_sessions(tmp_path):
    store = AuthStore(tmp_path / 'accounts.db', session_seconds=10)
    account = store.register('driver', 'long-password')
    token = store.create_session(account, now=100)
    assert AuthStore(store.path).session_user(token, now=105).username == 'driver'
    assert store.session_user(token, now=111) is None
    token = store.create_session(account)
    store.revoke(token)
    assert store.session_user(token) is None
    with sqlite3.connect(store.path) as connection:
        assert connection.execute('SELECT password_hash FROM users').fetchone()[0] != b'long-password'
        assert not connection.execute('SELECT 1 FROM sessions WHERE token_hash = ?', (token,)).fetchone()


def test_logout_closes_owned_webrtc_and_other_accounts_cannot_close_it(client, monkeypatch):
    monkeypatch.setattr(web, 'RTC_SESSIONS', {})
    monkeypatch.setattr(web.RTC, 'peers', {})
    closed = []

    async def offer(body):
        web.RTC.peers['peer'] = object()
        return web.api.RtcAnswer(peer_id='peer', sdp='v=0', type='answer')

    async def close(peer_id):
        closed.append(peer_id)
        web.RTC.peers.pop(peer_id, None)

    monkeypatch.setattr(web.RTC, 'offer', offer)
    monkeypatch.setattr(web.RTC, 'close', close)
    client.post('/api/auth/register', json={'username': 'first', 'password': 'long-password'})
    assert client.post('/api/rtc/offer', json={'run_id': 'abc123abc123', 'type': 'offer', 'sdp': 'v=0'}).status_code == 200
    other = TestClient(web.app, base_url='https://testserver')
    other.post('/api/auth/register', json={'username': 'second', 'password': 'long-password'})
    assert other.delete('/api/rtc/peer').status_code == 403
    client.post('/api/auth/logout')
    assert closed == ['peer'] and not web.RTC_SESSIONS


def test_login_lockout_and_existing_engineer_password_are_preserved(tmp_path):
    store = AuthStore(tmp_path / 'accounts.db')
    store.bootstrap_engineer('engineer', 'first-password')
    store.bootstrap_engineer('engineer', 'second-password')
    assert store.authenticate('engineer', 'first-password', now=100).role == 'engineer'
    for _ in range(5):
        assert store.authenticate('engineer', 'wrong-password', now=101) is None
    with pytest.raises(ValueError):
        store.authenticate('engineer', 'first-password', now=102)
    assert store.authenticate('engineer', 'first-password', now=402).role == 'engineer'
