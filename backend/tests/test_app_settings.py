import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import litellm
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select

from seoci import db as database
from seoci.app_settings import SECRET_FIELDS, resolve_settings
from seoci.config import settings
from seoci.db import Session
from seoci.models import AppSetting, AuditEvent
from seoci.providers import keywords, network, serp
from seoci.providers.llm import Intent, LiteLLMClient, MockLLMClient, get_llm
from tests.conftest import approve, detail, new_run, to_final


@pytest.fixture
def configured_env(client, monkeypatch):
    for key in ("llm_model", "llm_api_base", "llm_api_key", "dataforseo_login", "dataforseo_password", "github_token"):
        monkeypatch.setattr(settings, key, "")
    monkeypatch.setattr(settings, "github_api_url", "https://api.github.com")
    monkeypatch.setattr(settings, "serp_provider", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_read_write_secrets_and_field_only_audit(client, configured_env):
    initial = client.get("/api/settings")
    assert initial.headers["cache-control"] == "no-store"
    for name in SECRET_FIELDS:
        assert initial.json()[name] == {"configured": False, "source": "none"}
    secrets = {name: f"dummy-private-{name}-123456789" for name in SECRET_FIELDS}
    secrets["gsc_service_account_json"] = json.dumps({"type": "service_account", "client_email": "tester@example.com", "private_key": "dummy-private-gsc-key"})
    result = client.put("/api/settings", json={**secrets, "llm_model": "openai/custom", "llm_api_base": "http://localhost:8080/v1"})
    assert result.status_code == 200
    for response in (result, client.get("/api/settings")):
        for name, value in secrets.items():
            assert response.json()[name] == {"configured": True, "source": "db"}
            assert value not in response.text
            assert "dummy-private" not in response.text
    with Session() as db:
        audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "settings_updated"))
        assert audit.run_id is None
        assert audit.data == {"fields": sorted([*SECRET_FIELDS, "llm_model", "llm_api_base"])}
        assert not any(value in json.dumps(audit.data) for value in secrets.values())
        assert db.get(AppSetting, "llm_api_key").updated_at


def test_precedence_partial_updates_and_clear(client, configured_env, monkeypatch):
    monkeypatch.setattr(settings, "llm_model", "openai/env-model")
    monkeypatch.setattr(settings, "llm_api_base", "http://env.example/v1")
    monkeypatch.setattr(settings, "github_token", "dummy-env-token")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-openai-env")
    assert resolve_settings().values["llm_api_key"] == "dummy-openai-env"
    monkeypatch.setattr(settings, "llm_api_key", "dummy-generic-env")
    assert resolve_settings().values["llm_api_key"] == "dummy-generic-env"
    assert client.get("/api/settings").json()["github_token"] == {"configured": True, "source": "env"}
    client.put("/api/settings", json={"llm_model": "", "llm_api_base": "", "llm_api_key": "dummy-db-key", "github_token": "dummy-db-token"})
    snapshot = resolve_settings()
    assert snapshot.values["llm_model"] == ""
    assert snapshot.values["llm_api_base"] == ""
    assert snapshot.values["llm_api_key"] == "dummy-db-key"
    assert isinstance(get_llm(), MockLLMClient)
    client.put("/api/settings", json={"dataforseo_login": "owner@example.com"})
    assert resolve_settings().values["github_token"] == "dummy-db-token"
    result = client.put("/api/settings", json={"llm_model": None, "llm_api_key": None, "github_token": None}).json()
    assert result["llm_model"] == "openai/env-model"
    assert result["llm_api_key"] == {"configured": True, "source": "env"}
    assert resolve_settings().values["github_token"] == "dummy-env-token"
    assert result["dataforseo_login"] == "owner@example.com"
    assert isinstance(get_llm(), LiteLLMClient)
    with Session() as db:
        before = len(list(db.scalars(select(AuditEvent))))
    assert client.put("/api/settings", json={}).status_code == 200
    assert client.put("/api/settings", json={"github_token": None}).status_code == 200
    with Session() as db:
        assert len(list(db.scalars(select(AuditEvent)))) == before


@pytest.mark.parametrize("invalid", [
    {"serp_provider": "other"}, {"llm_api_base": "ftp://example.com"},
    {"llm_api_base": "http://user:dummy-private@example.com/v1"},
    {"github_api_url": "https://example.com?token=dummy-private"},
    {"github_api_url": "https://"}, {"github_api_url": "http://example.com:wrong"},
    {"github_api_url": ""}, {"llm_api_key": ""}, {"github_token": "   "},
    {"llm_api_key": ["dummy-private"]}, {"unknown": "dummy-private"},
])
def test_settings_validation_never_echoes_input(client, configured_env, invalid):
    result = client.put("/api/settings", json={"dataforseo_password": "dummy-private-password", **invalid})
    assert result.status_code == 422
    assert "dummy-private" not in result.text
    assert "input" not in result.text
    assert client.get("/api/settings").json()["dataforseo_password"]["configured"] is False


def test_factories_and_existing_llm_client_resolve_changes(client, configured_env, monkeypatch):
    assert isinstance(get_llm(), MockLLMClient)
    assert isinstance(serp.get_serp(), serp.MockSerp)
    completion = Mock(return_value=SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"label":"informational","reason":"Guide","confidence":0.8}'))],
    ))
    monkeypatch.setattr(litellm, "completion", completion)
    monkeypatch.setattr(litellm, "completion_cost", lambda **kwargs: 0)
    llm = LiteLLMClient()
    for suffix in ("first", "second"):
        assert client.put("/api/settings", json={"llm_model": f"openai/{suffix}", "llm_api_base": f"http://{suffix}.example/v1",
                          "llm_api_key": f"dummy-{suffix}", "serp_provider": "dataforseo"}).status_code == 200
        assert isinstance(get_llm(), LiteLLMClient)
        assert isinstance(serp.get_serp(), serp.DataForSEOSerp)
        assert isinstance(keywords.get_keywords(), keywords.DataForSEOKeywords)
        assert llm.complete_json("intent", "test", Intent).label == "informational"
        assert completion.call_args.kwargs["api_base"] == f"http://{suffix}.example/v1"
        assert completion.call_args.kwargs["api_key"] == f"dummy-{suffix}"
        assert completion.call_args.kwargs["model"] == f"openai/{suffix}"
    client.put("/api/settings", json={"llm_model": "", "serp_provider": "mock", "llm_api_key": None})
    assert isinstance(get_llm(), MockLLMClient)
    assert isinstance(keywords.get_keywords(), keywords.MockKeywords)
    assert "llm_api_key" not in {key for key in llm.usage[0]}


def test_dataforseo_resolves_both_auth_call_sites(client, configured_env, monkeypatch):
    request = Mock(return_value=SimpleNamespace(json=lambda: {"tasks": [{"status_code": 20000, "result": [
        {"country_iso_code": "ID", "location_type": "Country", "location_code": 2360}]}]}))
    monkeypatch.setattr(network, "request", request)
    for suffix in ("first", "second"):
        client.put("/api/settings", json={"dataforseo_login": suffix, "dataforseo_password": f"dummy-{suffix}"})
        network.dfs("test", {})
        assert request.call_args.kwargs["auth"] == (suffix, f"dummy-{suffix}")
    network.dfs_location("ID")
    assert request.call_args.kwargs["auth"] == ("second", "dummy-second")


def test_worker_error_does_not_persist_or_log_credentials(client, configured_env, project, monkeypatch, caplog):
    from seoci.worker import work_once
    secret = "dummy-private-provider-key-12345"
    client.put("/api/settings", json={"llm_model": "openai/custom", "llm_api_key": secret})
    monkeypatch.setattr(litellm, "completion", Mock(side_effect=ValueError(f"Remote error echoed {secret}")))
    run = new_run(client, project)
    assert work_once()
    result = detail(client, run)
    assert result["state"] == "failed"
    assert secret not in json.dumps(result)
    assert secret not in caplog.text


def test_exports_and_run_context_do_not_contain_credentials(client, configured_env, project):
    secret = "dummy-private-export-key-12345"
    values = {key: secret for key in SECRET_FIELDS}
    values["gsc_service_account_json"] = json.dumps({"type": "service_account", "client_email": "tester@example.com", "private_key": secret})
    assert client.put("/api/settings", json=values).status_code == 200
    run = to_final(client, project)
    approve(client, run, "final")
    assert secret not in json.dumps(detail(client, run))
    for kind in ("md", "html", "json"):
        result = client.get(f"/api/runs/{run}/export/{kind}")
        assert result.status_code == 200
        assert secret not in result.text


def test_github_uses_saved_endpoint_and_token(client, configured_env):
    from seoci.publish_github import publish
    client.put("/api/settings", json={"github_api_url": "https://github-api.example/v3", "github_token": "dummy-db-token"})
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.path.endswith("git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "base"}})
        if request.method == "GET":
            return httpx.Response(404)
        if request.url.path.endswith("pulls"):
            return httpx.Response(201, json={"html_url": "https://github.example/pr/1", "number": 1})
        return httpx.Response(201, json={})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        result = publish(SimpleNamespace(publishing={"github_repo": "owner/blog"}),
                         SimpleNamespace(id="run123456", primary_keyword="garden"),
                         SimpleNamespace(metadata_json={"title": "Garden", "slug": "garden"}, body_md="Garden"), "pass", client=http)
    assert result["pr_number"] == 1
    assert all(str(request.url).startswith("https://github-api.example/v3/") for request in calls)
    assert all(request.headers["Authorization"] == "Bearer dummy-db-token" for request in calls)


def test_migration_chain_upgrade_and_downgrade(tmp_path, monkeypatch):
    engine = database.make_engine(f"sqlite:///{tmp_path}/migration-settings.db")
    monkeypatch.setattr(database, "engine", engine)
    config = Config("alembic.ini")
    command.upgrade(config, "0003")
    command.upgrade(config, "head")
    assert "app_settings" in inspect(engine).get_table_names()
    columns = {column["name"]: column for column in inspect(engine).get_columns("audit_events")}
    assert columns["run_id"]["nullable"]
    command.downgrade(config, "0003")
    assert "app_settings" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    engine.dispose()
