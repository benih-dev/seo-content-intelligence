import json

from seoci.db import Session
from seoci.models import QAReview
from seoci.pipeline.graph import latest
from seoci.providers.llm import MockLLMClient
from tests.conftest import approve, to_final


def test_revision_prompt_contains_feedback(client, project, monkeypatch):
    run = to_final(client, project)
    finding = {"finding": "Explain the opening", "severity": "minor", "dimension": "Editorial quality", "location": "intro", "action": "Clarify"}
    with Session() as db:
        review = latest(db, QAReview, run)
        review.data = {**review.data, "findings": [finding]}
        db.commit()
    prompts = []
    original = MockLLMClient.complete_json
    def capture(self, task, prompt, schema):
        if task == "revise":
            prompts.append(json.loads(prompt))
        return original(self, task, prompt, schema)
    monkeypatch.setattr(MockLLMClient, "complete_json", capture)
    approve(client, run, "final", decision="request_revision", comment="Clarify the opening for apartment beginners")
    assert prompts[0].get("reviewer_comment") == "Clarify the opening for apartment beginners"
    assert prompts[0].get("revision_instructions") == prompts[0]["reviewer_comment"]
    assert prompts[0].get("qa_findings") == [finding]


def test_numeric_revision_instructions_reach_final_review(client, project):
    run = to_final(client, project)
    result = approve(client, run, "final", decision="request_revision", comment="Add 3 tips about pots")
    assert result["state"] == "final_review", result.get("error")
    assert len(result["drafts"]) == 2
    assert "Tanggapan atas arahan editor" in result["drafts"][-1]["body_md"]
    assert not any(finding["finding"] == "Unsupported numeric claim"
                   for finding in result["qa_reviews"][-1]["data"]["findings"])
