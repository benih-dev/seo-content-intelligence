from seoci.pipeline.quality import check_article
from seoci.providers.llm import MockLLMClient
from seoci.worker import work_once
from tests.conftest import approve, new_run


def test_empty_inventory_still_validates_project_links():
    result = check_article("# Guide\n\n[Related](https://example.com/missing)", {}, [], [], "guide", project_domain="https://example.com")
    assert any(f["finding"] == "Unknown internal link" for f in result["findings"])
    external = check_article("# Guide\n\n[Source](https://external.example/guide)", {}, [], [], "guide", project_domain="https://example.com")
    assert not any(f["finding"] == "Unknown internal link" for f in external["findings"])


def test_pipeline_checks_project_domain_without_inventory(client, project, monkeypatch):
    original = MockLLMClient.complete_json
    def add_unknown_link(self, task, prompt, schema):
        result = original(self, task, prompt, schema)
        if task in {"draft", "revise"}:
            result.body_md += "\n\n[Related](https://example.com/missing)"
        return result
    monkeypatch.setattr(MockLLMClient, "complete_json", add_unknown_link)
    run = new_run(client, project)
    work_once()
    approve(client, run, "keyword")
    result = approve(client, run, "brief")
    assert any(f["finding"] == "Unknown internal link" for f in result["qa_reviews"][-1]["data"]["findings"])
