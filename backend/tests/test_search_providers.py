import json
from datetime import date
from unittest.mock import Mock
from urllib.parse import quote

import httpx
import pytest
from sqlalchemy import select

from seoci.app_settings import resolve_settings
from seoci.config import settings
from seoci.db import Session
from seoci.models import KeywordMetricSnapshot
from seoci.pipeline.quality import opportunity
from seoci.providers import gsc, keywords, network, serp
from seoci.worker import work_once
from tests.conftest import detail, new_run

ACCOUNT = json.dumps({"type": "service_account", "client_email": "test@example.com", "private_key": "dummy-private-key"})


def mock_http(monkeypatch, handler):
    client = httpx.Client
    monkeypatch.setattr(network.httpx, "Client", lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))


def test_split_provider_fallback_and_runtime_precedence(client, monkeypatch):
    monkeypatch.setattr(settings, "keyword_provider", "")
    assert isinstance(keywords.get_keywords(), keywords.MockKeywords)
    client.put("/api/settings", json={"serp_provider": "dataforseo"})
    assert isinstance(keywords.get_keywords(), keywords.DataForSEOKeywords)
    monkeypatch.setattr(settings, "keyword_provider", "search_console")
    assert isinstance(keywords.get_keywords(), gsc.SearchConsoleKeywords)
    client.put("/api/settings", json={"keyword_provider": "mock", "serp_provider": "serper"})
    assert isinstance(serp.get_serp(), serp.SerperSerp)
    assert isinstance(keywords.get_keywords(), keywords.MockKeywords)
    client.put("/api/settings", json={"keyword_provider": None})
    assert isinstance(keywords.get_keywords(), gsc.SearchConsoleKeywords)
    monkeypatch.setattr(settings, "keyword_provider", "")
    assert isinstance(keywords.get_keywords(), keywords.MockKeywords)
    assert resolve_settings().public()["modes"]["keyword"] == "mock"


def test_serper_mapping_and_cache(client, monkeypatch):
    client.put("/api/settings", json={"serper_api_key": "dummy-serper"})
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://google.serper.dev/search"
        assert request.headers["X-API-KEY"] == "dummy-serper"
        assert json.loads(request.content) == {"q": "garden", "gl": "id", "hl": "id", "num": 10}
        return httpx.Response(200, json={"organic": [{"position": 2, "title": "Garden", "link": "https://example.com/guide", "snippet": "Tips"}],
                                        "peopleAlsoAsk": [{"question": "How?"}], "relatedSearches": [{"query": "balcony"}]})

    mock_http(monkeypatch, handler)
    result = serp.SerperSerp().search("garden", "id-ID")
    assert result["results"] == [{"rank": 2, "title": "Garden", "url": "https://example.com/guide", "snippet": "Tips"}]
    assert result["people_also_ask"] == [{"question": "How?"}]
    assert result["related_searches"] == [{"query": "balcony"}]
    assert serp.SerperSerp().search("garden", "id-ID") == result
    assert len(calls) == 1


@pytest.mark.parametrize("status,body", [(200, {}), (403, {"error": "dummy-private-key"})])
def test_serper_empty_and_error_are_safe(client, monkeypatch, status, body, caplog):
    client.put("/api/settings", json={"serper_api_key": "dummy-private-key"})
    mock_http(monkeypatch, lambda request: httpx.Response(status, json=body))
    with pytest.raises(RuntimeError, match="Serper request failed") as error:
        serp.SerperSerp().search("garden", "en-US")
    assert "dummy-private-key" not in str(error.value) + caplog.text


def configure_gsc(client, monkeypatch):
    assert client.put("/api/settings", json={"keyword_provider": "search_console", "gsc_site_url": "sc-domain:example.com",
                                            "gsc_service_account_json": ACCOUNT}).status_code == 200
    transport = Mock()
    monkeypatch.setattr(gsc, "Request", lambda: transport)
    credentials = Mock(token="dummy-access-token")
    credentials.refresh.side_effect = lambda callback: callback("https://oauth2.googleapis.com/token")
    factory = Mock(return_value=credentials)
    monkeypatch.setattr(gsc.service_account.Credentials, "from_service_account_info", factory)
    return factory, credentials, transport


def test_gsc_discovery_selected_metrics_cache_and_auth(client, monkeypatch):
    factory, credentials, transport = configure_gsc(client, monkeypatch)
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.raw_path.decode() == "/webmasters/v3/sites/" + quote("sc-domain:example.com", safe="") + "/searchAnalytics/query"
        assert request.headers["Authorization"] == "Bearer dummy-access-token"
        body = json.loads(request.content)
        assert body["dimensions"] == ["query"]
        assert (date.fromisoformat(body["endDate"]) - date.fromisoformat(body["startDate"])).days == 89
        if "dimensionFilterGroups" in body:
            assert body["dimensionFilterGroups"][0]["filters"][0] == {"dimension": "query", "operator": "equals", "expression": "garden"}
        return httpx.Response(200, json={"rows": [{"keys": ["garden"], "clicks": 12, "impressions": 400, "ctr": .03, "position": 4.2}]})

    mock_http(monkeypatch, handler)
    provider = gsc.SearchConsoleKeywords()
    assert provider.suggestions("unrelated seed", "en-US") == ["garden"]
    metric = provider.metrics(["garden"], "en-US")["garden"]
    assert metric["volume"] is None
    assert metric["impressions"] == 400 and metric["clicks"] == 12
    assert metric["ctr"] == .03 and metric["position"] == 4.2
    assert metric["provenance"] == "Search Console (own site)"
    provider.metrics(["garden"], "en-US")
    assert len(calls) == 2
    assert factory.call_args.kwargs["scopes"] == [gsc.SCOPE]
    assert credentials.refresh.call_count == 2
    assert transport.call_args.kwargs["timeout"] == settings.network_timeout


def test_gsc_empty_and_error_paths(client, monkeypatch, caplog):
    configure_gsc(client, monkeypatch)
    mock_http(monkeypatch, lambda request: httpx.Response(200, json={}))
    provider = gsc.SearchConsoleKeywords()
    metric = provider.metrics(["missing"], "en-US")["missing"]
    assert metric["volume"] is None and metric["impressions"] is None
    assert metric["status"] == "unavailable" and "not found" in metric["note"]
    with pytest.raises(RuntimeError, match="No Search Console queries"):
        provider.suggestions("seed", "en-US")
    monkeypatch.setattr(gsc.service_account.Credentials, "from_service_account_info", Mock(side_effect=ValueError(ACCOUNT)))
    with pytest.raises(RuntimeError, match="Search Console request failed") as error:
        provider.metrics(["different"], "en-US")
    assert "dummy-private" not in str(error.value) + caplog.text


def test_impressions_score_without_volume():
    metrics = {"provider": "search_console", "volume": None, "impressions": 400}
    score = opportunity(metrics, True)
    assert score["dimensions"]["demand_signals"]["score"] == 4
    assert "not search volume" in score["dimensions"]["demand_signals"]["reason"]
    assert score["confidence"] < opportunity({"volume": 400}, True)["confidence"]
    assert opportunity({**metrics, "impressions": None}, True)["dimensions"]["demand_signals"]["score"] is None


def test_gsc_keyword_pipeline_persists_real_metrics_without_volume(client, project, monkeypatch):
    configure_gsc(client, monkeypatch)
    mock_http(monkeypatch, lambda request: httpx.Response(200, json={"rows": [
        {"keys": ["garden"], "impressions": 400, "clicks": 12, "ctr": .03, "position": 4.2}]}))
    run = new_run(client, project, keyword="garden")
    assert work_once()
    result = detail(client, run)
    assert result["state"] == "keyword_review"
    metric = result["keywords"][0]["data"]["metrics"]
    assert metric["volume"] is None and metric["impressions"] == 400
    with Session() as db:
        rows = list(db.scalars(select(KeywordMetricSnapshot)))
        assert {row.metric_type: row.value for row in rows} == {
            "search_volume": None, "impressions": 400, "clicks": 12, "ctr": .03, "position": 4.2}
        assert all(row.geo == "own-site (all countries/languages)" for row in rows)


@pytest.mark.parametrize("patch", [
    {"keyword_provider": "invalid"}, {"serp_provider": "invalid"}, {"gsc_service_account_json": "dummy-private-invalid"},
    {"gsc_service_account_json": json.dumps({"type": "authorized_user", "private_key": "dummy-private"})},
    {"gsc_service_account_json": "[]"}, {"gsc_service_account_json": "{}"},
    {"gsc_site_url": "sc-domain:bad/path"}, {"gsc_site_url": "file:///dummy-private"},
    {"gsc_site_url": "https://owner:dummy-private@example.com/"},
])
def test_provider_validation_redacts_inputs(client, patch):
    response = client.put("/api/settings", json=patch)
    assert response.status_code == 422
    assert "dummy-private" not in response.text


def test_new_credentials_redaction_env_precedence_clear(client, monkeypatch):
    for key, value in (("serper_api_key", "dummy-env"), ("gsc_service_account_json", ACCOUNT)):
        monkeypatch.setattr(settings, key, value)
        assert client.get("/api/settings").json()[key] == {"configured": True, "source": "env"}
        assert client.put("/api/settings", json={key: value}).json()[key] == {"configured": True, "source": "db"}
        assert client.put("/api/settings", json={key: None}).json()[key] == {"configured": True, "source": "env"}
        assert value not in client.get("/api/settings").text
