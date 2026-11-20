from types import SimpleNamespace

import pytest

from seoci.pipeline.quality import WEIGHTS, opportunity, overlap
from seoci.providers.keywords import MockKeywords
from seoci.providers.llm import Intent
from seoci.worker import work_once
from tests.conftest import approve, detail, new_run


def test_discovery_without_seed(client, project, monkeypatch):
    monkeypatch.setattr(MockKeywords, "suggestions", lambda *args: ["balkon", "tomat"])
    run = new_run(client, project, mode="discovery")
    work_once()
    result = detail(client, run)
    assert [k["keyword"] for k in result["keywords"]] == ["balkon", "tomat"]
    result = approve(client, run, "keyword", payload={"keyword": "balkon"})
    assert result["primary_keyword"] == "balkon"


def test_candidate_overlap_at_gate(client, project):
    client.post(f"/api/projects/{project['id']}/content-items", json={"items": [
        {"url": "https://example.com/balkon", "title": "Balkon"}]})
    run = new_run(client, project, "balkon", mode="discovery")
    work_once()
    result = detail(client, run)
    assert result["state"] == "keyword_review"
    assert not any(a["stage"] == "strategy" for a in result["artifacts"])
    for candidate in result["keywords"]:
        assert "overlap_warnings" in candidate["data"]
        assert candidate["data"]["inventory_count"] == 1
    assert result["keywords"][0]["data"]["overlap_warnings"][0]["url"].endswith("/balkon")
    result = approve(client, run, "keyword")
    strategy = next(a for a in result["artifacts"] if a["stage"] == "strategy")
    assert strategy["data"]["overlap_warnings"]


@pytest.mark.parametrize("intent", [None, "", " ", "unsupported", [], 123])
def test_invalid_intent_has_no_side_effects(client, project, intent):
    run = new_run(client, project)
    work_once()
    before = detail(client, run)
    response = client.post(f"/api/runs/{run}/approve", json={"stage": "keyword", "payload": {"intent": intent}})
    assert response.status_code == 422
    after = detail(client, run)
    assert after["state"] == "keyword_review"
    assert after["approvals"] == before["approvals"]
    assert after["jobs"] == before["jobs"]


@pytest.mark.parametrize("raw,expected", [(" Commercial ", "commercial"), ("unknown", "mixed"), (None, "mixed"), ("", "mixed")])
def test_model_intent_normalization(raw, expected):
    assert Intent(label=raw, reason="SERP interpretation", confidence=.4).label == expected


def test_override_recomputes_score_preserves_inference(client, project):
    run = new_run(client, project)
    work_once()
    before = detail(client, run)["keywords"][0]
    result = approve(client, run, "keyword", payload={"intent": "commercial"})
    candidate = result["keywords"][0]
    assert candidate["data"]["intent"] == before["data"]["intent"]
    assert candidate["intent"] == candidate["data"]["final_intent"] == "commercial"
    score = candidate["data"]["opportunity"]
    assert score["dimensions"]["intent_fit"]["score"] == 50
    assert "commercial" in score["dimensions"]["intent_fit"]["reason"]
    assert candidate["score"] == score["score"] < before["score"]
    assert result["briefs"][0]["data"]["intent"] == "commercial"


@pytest.mark.parametrize("live,volume", [(True, 1000), (False, None)])
def test_unassessed_serp_excluded_from_total(live, volume):
    score = opportunity({"volume": volume}, live, intent="informational")
    dimension = score["dimensions"]["serp_attainability_gap"]
    assert dimension["score"] is None
    assert dimension["confidence"] <= .3
    assert "excluded from total" in dimension["reason"]
    available = {k: d["score"] for k, d in score["dimensions"].items() if d["score"] is not None}
    assert score["score"] == round(sum(WEIGHTS[k] * v for k, v in available.items()) / sum(WEIGHTS[k] for k in available), 1)


def test_inventory_update_preserves_metadata(client, project):
    path = f"/api/projects/{project['id']}/content-items"
    item = {"url": "https://example.com/balkon", "title": "Existing title", "slug": "custom-slug"}
    client.post(path, json={"items": [item]})
    result = client.post(path, json={"items": [{"url": item["url"]}]}).json()["items"][0]
    assert result["title"] == item["title"]
    assert result["slug"] == item["slug"]
    result = client.post(path, json={"items": [{"url": "https://example.com/path-only"}]}).json()["items"][0]
    assert result["slug"] == "path-only"
    assert overlap("balkon", [SimpleNamespace(url=item["url"], title="", slug="")])
    assert overlap("other", []) == []


def test_inventory_coverage_persisted(client, project):
    run = new_run(client, project)
    work_once()
    data = detail(client, run)["keywords"][0]["data"]
    assert data["inventory_count"] == 0
    assert data["overlap_warnings"] == []
    client.post(f"/api/projects/{project['id']}/content-items", json={"items": [{"url": "https://example.com/path"}]})
    run = new_run(client, project)
    work_once()
    assert detail(client, run)["keywords"][0]["data"]["inventory_missing_metadata"] == 1
