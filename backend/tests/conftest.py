import pytest
from fastapi.testclient import TestClient

from seoci import db
from seoci.api.main import app
from seoci.config import settings
from seoci import auth


@pytest.fixture(scope="session")
def user_hash():
    return auth.hash_password("test-password")


@pytest.fixture
def raw_client(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/test.db"
    engine = db.make_engine(url)
    monkeypatch.setattr(db, "engine", engine)
    db.Session.configure(bind=engine)
    monkeypatch.setattr(settings, "database_url", url)
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(settings, "serp_provider", "mock")
    monkeypatch.setattr(settings, "run_budget_usd", 2)
    monkeypatch.setattr(settings, "auth_users_file", str(tmp_path / "auth-users"))
    monkeypatch.setattr(settings, "auth_secret", "test-session-secret-with-at-least-32-characters")
    monkeypatch.setattr(auth, "throttle", auth.LoginThrottle())
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


@pytest.fixture
def client(raw_client, user_hash):
    auth.users_path().write_text(f"tester:{user_hash}\n")
    raw_client.cookies.set(auth.COOKIE, auth.create_session("tester", user_hash))
    return raw_client


@pytest.fixture
def project(client):
    response = client.post("/api/projects", json={"name": "Kebun", "domain": "https://example.com", "niche": "gardening",
                                                "audience": "pekebun pemula", "language": "id", "country": "ID"})
    assert response.status_code == 201
    return response.json()


def new_run(client, project, keyword="berkebun di balkon", mode="selected", headers=None):
    response = client.post("/api/runs", json={"project_id": project["id"], "primary_keyword": keyword, "mode": mode}, headers=headers or {})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def detail(client, run):
    return client.get(f"/api/runs/{run}").json()


def approve(client, run, stage, **kwargs):
    if stage == "final" and kwargs.get("decision", "approve") == "approve":
        draft = detail(client, run)["drafts"][-1]
        kwargs["payload"] = {"draft_id": draft["id"], "draft_version": draft["version"], **kwargs.get("payload", {})}
    response = client.post(f"/api/runs/{run}/approve", json={"stage": stage, **kwargs})
    assert response.status_code == 202, response.text
    from seoci.worker import work_once
    assert work_once()
    return detail(client, run)


def to_final(client, project, keyword="berkebun di balkon"):
    from seoci.worker import work_once
    run = new_run(client, project, keyword)
    assert work_once()
    assert detail(client, run)["state"] == "keyword_review"
    approve(client, run, "keyword")
    result = approve(client, run, "brief")
    assert result["state"] == "final_review", result.get("error")
    return run
