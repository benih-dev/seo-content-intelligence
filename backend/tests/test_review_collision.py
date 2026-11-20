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
