from concurrent.futures import ThreadPoolExecutor
import json
import stat

import pytest
from sqlalchemy import select

from seoci import auth
from seoci.config import settings
from seoci.db import Session
from seoci.models import AuditEvent


def setup(client, username="owner", password="test-password"):
    return client.post("/api/auth/setup", json={"username": username, "password": password})


def login(client, username="owner", password="test-password"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_first_run_authentication_and_logout(raw_client):
    assert raw_client.get("/api/health").status_code == 200
    assert raw_client.get("/api/auth/status").json() == {"setup_required": True}
    for path in ("/api/projects", "/api/settings", "/api/runs", "/api/auth/me", "/api/auth/unknown"):
        result = raw_client.get(path)
        assert result.status_code == 401
        assert result.json()["setup_required"] is True
    assert setup(raw_client).status_code == 201
    assert raw_client.get("/api/auth/status").json() == {"setup_required": False}
    assert raw_client.get("/api/settings").status_code == 401
    assert setup(raw_client, "second").status_code == 409
    assert login(raw_client, password="bad").status_code == 401
    result = login(raw_client)
    assert result.status_code == 200
    cookie = result.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=604800" in cookie
    assert raw_client.get("/api/auth/me").json() == {"username": "owner"}
    assert raw_client.get("/api/settings").status_code == 200
    assert raw_client.post("/api/auth/logout").status_code == 200
    assert raw_client.get("/api/projects").status_code == 401
    with Session() as db:
        events = list(db.scalars(select(AuditEvent)))
        assert {event.action for event in events} == {"auth_setup", "auth_login", "auth_login_failed"}
        assert "test-password" not in json.dumps([event.data for event in events])
        assert all(event.actor == "owner" for event in events)


def test_empty_file_setup_and_concurrent_first_users(raw_client):
    auth.users_path().write_text("\n")
    assert raw_client.get("/api/auth/status").json()["setup_required"] is True
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda name: auth.add_user(name, "test-password", first_only=True), ("one", "two")))
    assert sorted(results) == [False, True]
    assert len(auth.load_users()) == 1
    assert setup(raw_client).status_code == 409
    assert stat.S_IMODE(auth.users_path().stat().st_mode) == 0o600


def test_cli_hash_update_and_live_file_reload(raw_client, monkeypatch, capsys):
    monkeypatch.setattr(auth.getpass, "getpass", lambda prompt: "first-password")
    auth.main(["add-user", "owner"])
    first_hash = auth.load_users()["owner"]
    assert "first-password" not in auth.users_path().read_text()
    assert auth.verify_password("first-password", first_hash)
    assert not auth.verify_password("wrong-password", first_hash)
    assert login(raw_client, password="first-password").status_code == 200
    token = raw_client.cookies.get(auth.COOKIE)
    monkeypatch.setattr(auth.getpass, "getpass", lambda prompt: "new-password")
    auth.main(["add-user", "owner"])
    assert auth.load_users()["owner"] != first_hash
    assert raw_client.get("/api/auth/me").status_code == 401
    assert auth.session_user(token) is None
    assert login(raw_client, password="first-password").status_code == 401
    assert login(raw_client, password="new-password").status_code == 200
    assert "password" not in capsys.readouterr().out
    monkeypatch.setattr(auth.getpass, "getpass", lambda prompt: "another-password")
    auth.main(["add-user", "another"])
    assert len(auth.load_users()) == 2
    assert setup(raw_client).status_code == 409


def test_password_rotation_during_login_invalidates_issued_session(raw_client, monkeypatch):
    setup(raw_client)
    verify = auth.verify_password

    def verify_then_rotate(password, encoded):
        valid = verify(password, encoded)
        auth.add_user("owner", "rotated-password")
        return valid

    monkeypatch.setattr(auth, "verify_password", verify_then_rotate)
    assert login(raw_client).status_code == 200
    assert auth.session_user(raw_client.cookies.get(auth.COOKIE)) is None
    assert raw_client.get("/api/auth/me").status_code == 401
    monkeypatch.setattr(auth, "verify_password", verify)
    assert login(raw_client, password="rotated-password").status_code == 200


def test_throttle_per_username_and_ip(raw_client, monkeypatch):
    setup(raw_client)
    for _ in range(5):
        assert login(raw_client, password="wrong-password").status_code == 401
    assert login(raw_client).status_code == 429
    assert login(raw_client, username="other", password="wrong-password").status_code == 401
    assert not auth.throttle.blocked(("owner", "different-ip"))
    now = auth.time.monotonic()
    monkeypatch.setattr(auth.time, "monotonic", lambda: now + 901)
    assert login(raw_client).status_code == 200


def test_signed_expired_and_revoked_sessions(raw_client, monkeypatch):
    setup(raw_client)
    login(raw_client)
    token = raw_client.cookies.get(auth.COOKIE)
    assert auth.session_user(token) == "owner"
    for invalid in ("", "malformed", token + "tamper", "a.b.c", "☃.☃"):
        assert auth.session_user(invalid) is None
    now = auth.time.time()
    monkeypatch.setattr(auth.time, "time", lambda: now + auth.SESSION_SECONDS + 1)
    assert auth.session_user(token) is None


def test_persistent_secret_and_env_override(raw_client, monkeypatch):
    monkeypatch.setattr(settings, "auth_secret", "")
    setup(raw_client)
    login(raw_client)
    token = raw_client.cookies.get(auth.COOKIE)
    secret = auth.signing_secret()
    assert secret == auth.signing_secret()
    secret_path = auth.users_path().with_name(auth.users_path().name + ".secret")
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600
    assert auth.session_user(token) == "owner"
    monkeypatch.setattr(settings, "auth_secret", "different-secret-from-environment")
    assert auth.session_user(token) is None


@pytest.mark.parametrize("body", [
    {"username": "bad:name", "password": "dummy-private-password"},
    {"username": "owner", "password": "short"},
    {"username": "owner", "password": ["dummy-private-password"]},
])
def test_safe_validation_errors(raw_client, body):
    response = raw_client.post("/api/auth/setup", json=body)
    assert response.status_code == 422
    assert "dummy-private" not in response.text
    assert "input" not in response.text
    assert not auth.load_users()


def test_malformed_users_file_fails_closed(raw_client):
    auth.users_path().write_text("not a valid account line\n")
    assert raw_client.get("/api/auth/status").status_code == 503
    assert setup(raw_client).status_code == 503
    assert raw_client.get("/api/settings").status_code == 503
    assert auth.users_path().read_text() == "not a valid account line\n"


def test_secure_cookie_and_cross_site_rejection(raw_client):
    assert raw_client.post("/api/auth/setup", json={"username": "owner", "password": "test-password"},
                           headers={"sec-fetch-site": "cross-site"}).status_code == 403
    setup(raw_client)
    response = raw_client.post("/api/auth/login", json={"username": "owner", "password": "test-password"},
                               headers={"x-forwarded-proto": "https"})
    assert "Secure" in response.headers["set-cookie"]
