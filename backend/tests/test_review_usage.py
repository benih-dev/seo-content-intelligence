import pytest

from seoci.config import settings
from seoci.db import Session
from seoci.models import WorkflowRun
from seoci.pipeline import graph
from seoci.providers.llm import Intent
from tests.conftest import detail, new_run


@pytest.mark.parametrize("invalid", [False, True])
def test_paid_usage_survives_failed_stage(client, project, monkeypatch, invalid):
    run_id = new_run(client, project)
    class PaidClient:
        usage = []
        def complete_json(self, *args):
            self.usage = [{"cost_usd": .75, "prompt_tokens": 10, "completion_tokens": 5}]
            if invalid:
                raise ValueError("invalid provider JSON")
            return Intent(label="informational", reason="test", confidence=.5)
    monkeypatch.setattr(graph, "get_llm", PaidClient)
    def broken(db, run):
        graph.llm_call(db, run, "intent", Intent)
        raise RuntimeError("later stage failure")
    with pytest.raises((ValueError, RuntimeError)):
        graph.stage("paid_failure", broken)({"run_id": run_id})
    assert detail(client, run_id)["usage"]["cost_usd"] == .75
    monkeypatch.setattr(settings, "run_budget_usd", .5)
    with Session() as db, pytest.raises(RuntimeError, match="budget exhausted"):
        graph.llm_call(db, db.get(WorkflowRun, run_id), "intent", Intent)
