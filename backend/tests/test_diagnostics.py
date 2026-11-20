import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import litellm
import pytest
from sqlalchemy import select, func

from tests.conftest import new_run, detail
from seoci.db import Session
from seoci.diagnostics import classify, redact, persist_events, record_event, RedactingFilter
from seoci.models import AuditEvent, DiagnosticEvent, Job, WorkflowRun
from seoci.providers import serp, network
from seoci.worker import work_once


def status_error(status, message="provider error"):
    request = httpx.Request("POST", "https://user:password@example.com/v1?key=secret-query")
    return httpx.HTTPStatusError(message, request=request, response=httpx.Response(status, request=request))


@pytest.mark.parametrize("exc,category,status", [
    (status_error(401), "auth", 401), (status_error(403), "auth", 403),
    (status_error(404), "model_not_found", 404), (status_error(400, "unsupported model"), "model_not_found", 400),
    (httpx.ConnectError("DNS failed"), "unreachable", None), (httpx.ReadTimeout("too slow"), "timeout", None),
    (status_error(429), "rate_limit", 429), (status_error(400, "response_format"), "bad_request", 400),
    (json.JSONDecodeError("bad", "private output", 0), "invalid_output", None),
    (RuntimeError("unexpected"), "unknown", None),
])
def test_classification(exc, category, status):
    error = classify(exc, "LLM", "openai/custom", "https://user:password@example.com:8080/v1?key=secret-query", {})
    assert error["category"] == category
    assert error["status"] == status
    assert "LLM" in error["message"] and "openai/custom" in error["message"]
    assert error["hint"]
    assert not any(value in json.dumps(error) for value in ("password", "secret-query", "private output"))
    if category == "unreachable":
        assert "example.com" in error["message"] and ":8080" not in error["message"]


def test_redactor():
    key = "fake-key-without-a-prefix"
    account = json.dumps({"client_email": "private@example.com", "private_key": "PRIVATE-KEY-CONTENT"})
    message = f'{key} sk-secret-token Bearer access-token Authorization: header-secret\nX-API-KEY: second-secret\n{account} https://user:pass@host.test/path?token=query-secret'
    safe = redact(message, {"llm_api_key": key, "gsc_service_account_json": account})
    for secret in (key, "sk-secret-token", "access-token", "header-secret", "second-secret", account, "PRIVATE-KEY-CONTENT", "private@example.com", "query-secret", "user:pass"):
        assert secret not in safe


def test_failure_persistence_and_redaction(client, project, monkeypatch, caplog):
    key = "injected-fake-provider-key"
    client.put("/api/settings", json={"llm_model": "openai/custom", "llm_api_base": "http://127.0.0.1:9/v1", "llm_api_key": key})
    def fail(**kwargs):
        logging.getLogger("test-provider").error("Authorization: Bearer %s https://user:pass@example.com?key=other-secret", key)
        raise status_error(401, f"Key {key} rejected")
    monkeypatch.setattr(litellm, "completion", fail)
    run_id = new_run(client, project)
    assert work_once()
    run = detail(client, run_id)
    error = run["error_details"]
    assert run["state"] == "failed" and error["category"] == "auth"
    assert error["stage"] == "keyword_research" and error["attempt"] == 1 and error["timestamp"]
    assert run["jobs"][0]["error_details"] == error
    assert any(row["action"] == "job_error" and row["data"] == error for row in run["audit"])
    response = client.get("/api/logs", params={"run_id": run_id, "level": "error"})
    assert response.status_code == 200 and response.json()
    assert all(row["level"] == "error" and row["run_id"] == run_id for row in response.json())
    with Session() as db:
        stored = json.dumps({
            "events": [row.data for row in db.scalars(select(DiagnosticEvent))],
            "audit": [row.data for row in db.scalars(select(AuditEvent))],
            "run": db.get(WorkflowRun, run_id).error_details,
            "jobs": [row.error_details for row in db.scalars(select(Job))],
        })
    for value in (key, "other-secret", "user:pass"):
        assert value not in stored + response.text + json.dumps(run) + caplog.text
    assert client.post(f"/api/runs/{run_id}/retry").status_code == 202
    assert detail(client, run_id)["error_details"] is None


def test_logs_auth_filters_and_retention(client):
    assert client.get("/api/logs").json() == []
    rows = [{"time": f"2026-01-01T00:{i:04}", "level": "error" if i % 2 else "info", "run_id": "run-a" if i % 3 else "run-b", "message": "safe"} for i in range(505)]
    persist_events(rows)
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(DiagnosticEvent)) == 500
    filtered = client.get("/api/logs?run_id=run-a&level=error").json()
    assert filtered and all(r["run_id"] == "run-a" and r["level"] == "error" for r in filtered)
    assert client.get("/api/logs?run_id=unknown").json() == []
    assert client.get("/api/logs?level=debug").status_code == 422
    client.cookies.clear()
    assert client.get("/api/logs").status_code == 401
    assert client.post("/api/settings/test/llm").status_code == 401


@pytest.mark.parametrize("kind", ["llm", "serp", "keyword"])
def test_connection_mock_success(client, kind):
    result = client.post(f"/api/settings/test/{kind}")
    assert result.status_code == 200 and result.json()["ok"] is True
    assert "mock" in result.json()["message"]


def test_live_connection_tests(client, monkeypatch):
    client.put("/api/settings", json={"llm_model": "openai/custom", "llm_api_key": "fake-test-key", "serp_provider": "serper", "serper_api_key": "fake-serper-key"})
    completion = Mock(return_value=SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1), choices=[SimpleNamespace(message=SimpleNamespace(content='{"reply":"ok"}'))]))
    monkeypatch.setattr(litellm, "completion", completion)
    monkeypatch.setattr(litellm, "completion_cost", Mock(return_value=0))
    assert client.post("/api/settings/test/llm").json()["ok"]
    assert completion.call_args.kwargs["max_tokens"] == 32
    completion.side_effect = status_error(400, "fake-test-key response_format unsupported")
    result = client.post("/api/settings/test/llm").json()
    assert result["category"] == "bad_request" and "fake-test-key" not in json.dumps(result)
    monkeypatch.setattr(serp, "request", Mock(side_effect=status_error(403, "fake-serper-key")))
    result = client.post("/api/settings/test/serp").json()
    assert not result["ok"] and result["category"] == "auth"
    client.put("/api/settings", json={"keyword_provider": "dataforseo"})
    monkeypatch.setattr(network, "request", Mock(side_effect=status_error(429)))
    result = client.post("/api/settings/test/keyword").json()
    assert result["category"] == "rate_limit"


def test_unknown_pipeline_failure_is_sanitized(client, project, monkeypatch):
    import seoci.worker as worker
    monkeypatch.setattr(worker, "execute", Mock(side_effect=RuntimeError("sk-pipeline-secret")))
    run_id = new_run(client, project)
    worker.work_once()
    result = detail(client, run_id)
    assert result["error_details"]["category"] == "unknown"
    assert "sk-pipeline-secret" not in json.dumps(result)


def test_python_event_logging(client, caplog):
    with caplog.at_level(logging.INFO):
        record_event(message="Provider call succeeded", provider="test")
    assert "Provider call succeeded" in caplog.text


def test_non_json_model_output(client, monkeypatch):
    client.put("/api/settings", json={"llm_model": "openai/custom"})
    completion = Mock(return_value=SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1), choices=[SimpleNamespace(message=SimpleNamespace(content="sk-secret-model-output"))]))
    monkeypatch.setattr(litellm, "completion", completion)
    monkeypatch.setattr(litellm, "completion_cost", Mock(return_value=0))
    response = client.post("/api/settings/test/llm")
    assert response.json()["category"] == "invalid_output"
    assert completion.call_count == 2
    assert "sk-secret-model-output" not in response.text + client.get("/api/logs").text


def test_wrapped_litellm_connection_error():
    exc = litellm.InternalServerError(message="OpenAIException - Connection error.", model="openai/custom", llm_provider="openai")
    result = classify(exc, "LLM", "openai/custom", "http://127.0.0.1:9/v1", {})
    assert result["category"] == "unreachable" and result["status"] is None
    assert "127.0.0.1" in result["message"]


def test_redacting_filter_preserves_access_log_arguments():
    from uvicorn.logging import AccessFormatter
    record = logging.LogRecord("uvicorn.access", logging.INFO, "test", 1, '%s - "%s %s HTTP/%s" %d',
                               ("127.0.0.1", "GET", "/api/logs?token=sk-private", "1.1", 200), None)
    assert RedactingFilter().filter(record)
    text = AccessFormatter().format(record)
    assert "sk-private" not in text and len(record.args) == 5
