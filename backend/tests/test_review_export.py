from seoci.pipeline import graph
from seoci.worker import work_once
from tests.conftest import approve, detail, to_final


def test_export_failure_can_retry(client, project, monkeypatch):
    run = to_final(client, project)
    original = graph.build_exports
    def broken(*args):
        raise OSError("export storage unavailable")
    monkeypatch.setattr(graph, "build_exports", broken)
    failed = approve(client, run, "final")
    assert failed["state"] == "failed"
    assert failed["jobs"][-1]["status"] == "failed"
    monkeypatch.setattr(graph, "build_exports", original)
    assert client.post(f"/api/runs/{run}/retry").status_code == 202
    assert work_once()
    assert detail(client, run)["state"] == "exported"
