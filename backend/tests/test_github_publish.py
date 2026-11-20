import base64
import json
from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from seoci.api import main
from seoci.config import settings
from seoci.db import Session
from seoci.models import ArticleDraft, Project, WorkflowRun
from seoci.publish_github import blog_file, publish


@pytest.fixture
def ready(client, project, monkeypatch):
    monkeypatch.setattr(settings, "github_token", "test-token")
    with Session() as db:
        db.get(Project, project["id"]).publishing = {"github_repo": "owner/blog"}
        run = WorkflowRun(project_id=project["id"], mode="selected", primary_keyword="kebun",
                          locale="id-ID", state="exported")
        db.add(run)
        db.flush()
        db.add(ArticleDraft(run_id=run.id, body_md="# Body\n\nLatest article.", metadata_json={
            "title": 'Kebun: "praktis"', "meta_description": "Baris satu\nBaris dua", "slug": "kebun",
            "tags": ["kebun", "tips: mudah"]}))
        db.commit()
        return run.id


def mock_github(monkeypatch, handler):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(main, "publish", lambda *args: publish(*args, client=client))
    return client


def test_happy_path_and_repeat(client, ready, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        path = request.url.path
        if path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "base-sha"}})
        if request.method == "GET":
            assert request.url.params["ref"] == "main"
            return httpx.Response(404)
        body = json.loads(request.content)
        if path.endswith("/git/refs"):
            assert body == {"ref": f"refs/heads/seoci/kebun-{ready[:8]}", "sha": "base-sha"}
        elif request.method == "PUT":
            assert path.endswith("/contents/src/content/blog/kebun.md")
            assert body["branch"] != "main"
            content = base64.b64decode(body["content"]).decode()
            assert content == ('---\ntitle: "Kebun: \\"praktis\\""\n'
                               'description: "Baris satu\\nBaris dua"\n'
                               f'pubDate: {date.today().isoformat()}\n'
                               'tags: ["kebun", "tips: mudah"]\n---\n\n# Body\n\nLatest article.\n')
        else:
            assert path.endswith("/pulls")
            assert body["base"] == "main"
            assert body["title"] == 'Kebun: "praktis"'
            assert ready in body["body"] and "Needs human review" in body["body"]
            return httpx.Response(201, json={"html_url": "https://github.com/owner/blog/pull/7", "number": 7})
        return httpx.Response(201, json={})

    with mock_github(monkeypatch, handler):
        response = client.post(f"/api/runs/{ready}/publish/github")
        assert response.status_code == 200, response.text
        assert len(requests) == 5
        assert response.json()["pr_number"] == 7
        assert client.post(f"/api/runs/{ready}/publish/github").json() == response.json()
        assert len(requests) == 5
        detail = client.get(f"/api/runs/{ready}").json()
        assert detail["github_publish"] == response.json()
        assert detail["state"] == "exported"


def test_not_approved(client, ready):
    with Session() as db:
        db.get(WorkflowRun, ready).state = "final_review"
        db.commit()
    assert client.post(f"/api/runs/{ready}/publish/github").status_code == 409


@pytest.mark.parametrize("missing", ["repo", "token"])
def test_missing_config(client, ready, monkeypatch, missing):
    if missing == "repo":
        with Session() as db:
            run = db.get(WorkflowRun, ready)
            db.get(Project, run.project_id).publishing = {}
            db.commit()
    else:
        monkeypatch.setattr(settings, "github_token", "")
    response = client.post(f"/api/runs/{ready}/publish/github")
    assert response.status_code == 400
    assert ("github_repo" if missing == "repo" else "GITHUB_TOKEN") in response.json()["detail"]


def test_existing_file(client, ready, monkeypatch):
    def handler(request):
        assert request.method == "GET"
        return httpx.Response(200, json={"object": {"sha": "base-sha"}})
    with mock_github(monkeypatch, handler):
        response = client.post(f"/api/runs/{ready}/publish/github")
        assert response.status_code == 409
        assert "File already exists" in response.json()["detail"]


@pytest.mark.parametrize("status,text", [(401, "authentication"), (403, "permissions"),
                                         (404, "not found"), (422, "rejected")])
def test_github_errors(client, ready, monkeypatch, status, text):
    with mock_github(monkeypatch, lambda request: httpx.Response(status, json={"message": "private detail"})):
        response = client.post(f"/api/runs/{ready}/publish/github")
        assert response.status_code == 502
        assert text in response.json()["detail"]
        assert "private detail" not in response.text
        assert "test-token" not in response.text


def test_network_error(client, ready, monkeypatch):
    def handler(request):
        raise httpx.ConnectError("private detail", request=request)
    with mock_github(monkeypatch, handler):
        response = client.post(f"/api/runs/{ready}/publish/github")
        assert response.status_code == 502
        assert "could not be reached" in response.json()["detail"]


def test_empty_metadata():
    slug, content = blog_file(SimpleNamespace(metadata_json={}, body_md="Body"))
    assert slug == "untitled-article"
    assert 'description: ""' in content
    assert "tags:" not in content


@pytest.mark.parametrize("publishing", [{"github_repo": "bad"}, {"content_dir": "../blog"},
                                       {"content_dir": "/blog"}, {"content_dir": "a/../b"},
                                       {"file_extension": "html"}])
def test_invalid_project_publishing(client, project, publishing):
    response = client.put(f"/api/projects/{project['id']}", json={**project, "publishing": publishing})
    assert response.status_code == 422
