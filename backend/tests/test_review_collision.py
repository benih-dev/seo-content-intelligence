import pytest

from seoci.pipeline.quality import available_slug, check_article
from tests.conftest import detail, to_final


def test_generated_slug_avoids_existing_inventory(client, project):
    url = "https://example.com/berkebun-di-balkon"
    client.post(f"/api/projects/{project['id']}/content-items", json={"items": [{"url": url, "title": "Berkebun di balkon"}]})
    run = to_final(client, project)
    assert detail(client, run)["drafts"][-1]["metadata_json"]["slug"] != "berkebun-di-balkon"


@pytest.mark.parametrize("href", ["https://example.com/guide", "https://example.com/guide/?ref=test#section", "/guide", "guide"])
def test_qa_rejects_self_link_even_when_inventory_contains_it(href):
    url = "https://example.com/guide"
    result = check_article(f"# Guide\n\n[Related]({href})", {"slug": "guide"}, [], [url], "guide", project_domain="https://example.com")
    assert any(f["finding"] == "Self-referencing internal link" for f in result["findings"])
    assert any(f["finding"] == "Slug collides with existing content" for f in result["findings"])


def test_slug_suffix_uses_available_path():
    assert available_slug("guide", "https://example.com", []) == "guide"
    assert available_slug("guide", "https://example.com", ["https://example.com/guide/", "https://example.com/guide-2"]) == "guide-3"


def test_www_inventory_alias_is_the_same_site_for_slug_and_link_checks():
    domain = "https://example.com"
    inventory = ["https://www.example.com/guide", "https://www.example.com/known"]
    assert available_slug("guide", domain, inventory) == "guide-2"
    body = "# Guide\n\n[Known](https://example.com/known) [Missing](https://www.example.com/missing)"
    result = check_article(body, {"slug": "guide"}, [], inventory, "gardening", project_domain=domain)
    assert any(f["finding"] == "Slug collides with existing content" for f in result["findings"])
    assert [f["location"] for f in result["findings"] if f["finding"] == "Unknown internal link"] == [
        "https://www.example.com/missing",
    ]
