from seoci.worker import work_once
from tests.conftest import approve, detail, new_run

INVENTORY = [{"url": "https://example.com/perawatan-balkon", "title": "Berkebun di balkon: catatan perawatan", "slug": "perawatan-balkon"},
             {"url": "https://example.com/media-tanam", "title": "Memilih media tanam untuk pot", "slug": "media-tanam"}]


def brief_run(client, project):
    assert client.post(f"/api/projects/{project['id']}/content-items", json={"items": INVENTORY}).status_code == 200
    run = new_run(client, project)
    work_once()
    return run, approve(client, run, "keyword")


def submit(client, run, edits):
    return client.post(f"/api/runs/{run}/approve", json={"stage": "brief", "payload": {"edits": edits}})


def test_generated_brief_covers_strategy_outline_and_inventory_links(client, project):
    run, result = brief_run(client, project)
    brief = result["briefs"][-1]["data"]
    assert brief["rationale"] and brief["differentiation"]
    assert all(x["purpose"] for x in brief["outline"])
    assert len({x["purpose"] for x in brief["outline"]}) == len(brief["outline"])
    assert brief["subtopics"] and brief["entities"] and brief["examples"] and brief["exclusions"]
    assert brief["internal_links"] == [{"url": INVENTORY[0]["url"], "title": INVENTORY[0]["title"], "anchor": INVENTORY[0]["title"],
                                        "reason": "Related article in your inventory; shares: balkon, berkebun", "status": "inventory"}]


def test_brief_links_outside_inventory_become_search_suggestions(client, project):
    run, result = brief_run(client, project)
    edits = {**result["briefs"][-1]["data"], "internal_links": [
        {"url": "https://example.com/media-tanam/", "anchor": "media tanam"},
        "https://example.com/belum-ada",
        {"url": "", "anchor": "Cara memilih pot", "status": "inventory"},
        {"url": "", "anchor": "  "}]}
    assert submit(client, run, edits).status_code == 202
    work_once()
    brief = detail(client, run)["briefs"][-1]
    assert brief["status"] == "approved" and brief["version"] == 2
    links = brief["data"]["internal_links"]
    assert [(x["url"], x["anchor"], x["status"]) for x in links] == [
        ("https://example.com/media-tanam", "media tanam", "inventory"),
        ("https://example.com/belum-ada", "https://example.com/belum-ada", "search_suggestion"),
        ("", "Cara memilih pot", "search_suggestion")]
    draft = detail(client, run)["drafts"][-1]["body_md"]
    assert "(https://example.com/media-tanam)" in draft and "belum-ada" not in draft


def test_unchanged_brief_approves_existing_version(client, project):
    run, result = brief_run(client, project)
    assert submit(client, run, result["briefs"][-1]["data"]).status_code == 202
    work_once()
    result = detail(client, run)
    assert [(x["version"], x["status"]) for x in result["briefs"]] == [(1, "approved")]
    assert any(x["data"].get("reason") == "Brief v1 approved" for x in result["audit"] if x["action"] == "transition")


def test_brief_edits_are_cleaned_and_errors_are_readable(client, project):
    run, result = brief_run(client, project)
    data = result["briefs"][-1]["data"]
    skipped = [{"level": 1, "heading": "H1", "purpose": "Intro"}, {"level": 3, "heading": "Detail", "purpose": "Depth"}]
    response = submit(client, run, {"outline": skipped})
    assert response.status_code == 422
    assert response.json()["detail"] == "“Detail” skips a heading level; use H2 or lower"
    response = submit(client, run, {"outline": [*data["outline"], {"level": 2, "heading": "Tips", "purpose": " "}]})
    assert response.json()["detail"] == "Add a section purpose for “Tips”"
    response = submit(client, run, {"intent": "buying", "angle": " "})
    assert response.status_code == 422
    assert "Angle: String should have at least 1 character" in response.json()["detail"]
    assert "Intent: Search intent must be one of" in response.json()["detail"]
    assert submit(client, run, {"questions": ["Apa itu?", "", "Apa itu?", "  Kapan?  "], "intent": "Commercial"}).status_code == 202
    work_once()
    brief = detail(client, run)["briefs"][-1]["data"]
    assert brief["questions"] == ["Apa itu?", "Kapan?"] and brief["intent"] == "commercial"


def test_link_keys_keep_queries_and_tolerate_malformed_urls():
    from types import SimpleNamespace

    from seoci.pipeline.quality import annotate_internal_links
    inventory = [SimpleNamespace(url=f"https://example.com/post?id={i}", title=f"Post {i}", slug="") for i in (1, 2)]
    links = annotate_internal_links([{"url": "https://example.com/post?id=1"}, {"url": "https://example.com/post?id=2"},
                                     {"url": "https://[example.com/broken"}], inventory)
    assert [(x["url"], x["status"]) for x in links] == [("https://example.com/post?id=1", "inventory"),
                                                        ("https://example.com/post?id=2", "inventory"),
                                                        ("https://[example.com/broken", "search_suggestion")]


def test_inventory_link_keys_preserve_path_and_query_case():
    from types import SimpleNamespace

    from seoci.pipeline.quality import annotate_internal_links
    urls = ["https://example.com/Guide?ref=A", "https://example.com/guide?ref=A", "https://example.com/guide?ref=a"]
    inventory = [SimpleNamespace(url=url, title=url, slug="") for url in urls]
    links = annotate_internal_links([{"url": url.replace("https://example.com", "HTTPS://EXAMPLE.COM")} for url in urls], inventory)
    assert [(link["url"], link["status"]) for link in links] == [(url, "inventory") for url in urls]


def test_brief_schema_tells_live_models_the_required_outline_shape():
    from seoci.providers.llm import Brief
    outline = Brief.model_json_schema()["properties"]["outline"]
    assert outline["minItems"] == 2
    assert "exactly one H1" in outline["description"]
    item = outline["items"]
    assert set(item["required"]) == {"level", "heading", "purpose"}
    assert item["properties"]["level"] == {"type": "integer", "enum": [1, 2, 3]}
    for field in ("heading", "purpose"):
        assert item["properties"][field] == {"type": "string", "minLength": 1}


def test_outline_text_fields_are_coerced_or_rejected():
    import pytest
    from pydantic import ValidationError

    from seoci.providers.llm import Brief
    base = {"angle": "a", "audience": "b", "intent": "informational", "questions": [], "exclusions": [],
            "internal_links": [], "source_plan": []}
    brief = Brief.model_validate({**base, "outline": [{"level": 1, "heading": 2026, "purpose": 1}, {"level": 2, "heading": "B", "purpose": 3.5}]})
    assert [(x["heading"], x["purpose"]) for x in brief.outline] == [("2026", "1"), ("B", "3.5")]
    with pytest.raises(ValidationError, match="Outline purposes must be text"):
        Brief.model_validate({**base, "outline": [{"level": 1, "heading": "A", "purpose": ["x"]}, {"level": 2, "heading": "B", "purpose": "y"}]})
