"""Seed the running API/worker with a reviewable run and an exported article."""
import json
import os
import time
from urllib.request import Request, urlopen

BASE = os.environ.get("API_URL", "http://127.0.0.1:8000")


def call(path, body=None, key=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    request = Request(BASE + "/api" + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def wait(run_id, state):
    for _ in range(300):
        run = call(f"/runs/{run_id}")
        if run["state"] in {"failed", "blocked"}:
            raise RuntimeError(run["error"] or str(run["qa_reviews"]))
        if run["state"] == state and not any(j["status"] in {"pending", "running"} for j in run["jobs"]):
            return run
        time.sleep(.2)
    raise TimeoutError(state)


def main():
    projects = call("/projects")
    project = next((p for p in projects if p["name"] == "Kebun Balkon"), None)
    if not project:
        project = call("/projects", {"name": "Kebun Balkon", "domain": "https://kebun.example", "niche": "Berkebun di ruang terbatas", "audience": "Pemula yang tinggal di apartemen", "language": "id", "country": "ID", "voice_profile": "Ramah, jelas, praktis. Tanpa janji hasil atau statistik rekaan.", "business_objective": "Membantu pembaca membangun kebun balkon yang sesuai kondisi mereka."})
        call(f"/projects/{project['id']}/content-items", {"items": [{"url": "https://kebun.example/media-tanam", "title": "Memilih media tanam untuk pot", "slug": "media-tanam"}, {"url": "https://kebun.example/perawatan-balkon", "title": "Berkebun di balkon: catatan perawatan", "slug": "perawatan-balkon"}]})
    runs = call(f"/runs?project_id={project['id']}")
    exported = next((r for r in runs if r["state"] == "exported"), None)
    if not exported:
        exported = call("/runs", {"project_id": project["id"], "primary_keyword": "berkebun di balkon", "mode": "selected"}, f"{project['id']}:exported")
        for state, stage in [("keyword_review", "keyword"), ("brief_review", "brief"), ("final_review", "final")]:
            wait(exported["id"], state)
            call(f"/runs/{exported['id']}/approve", {"stage": stage, "comment": "Demo editorial review — source limitations acknowledged"})
        wait(exported["id"], "exported")
    pending = next((r for r in runs if r["state"] == "keyword_review"), None)
    if not pending:
        pending = call("/runs", {"project_id": project["id"], "primary_keyword": "berkebun di balkon", "mode": "discovery"}, f"{project['id']}:review:{len(runs)}")
        wait(pending["id"], "keyword_review")
    print(json.dumps({"project_id": project["id"], "keyword_review_run": pending["id"], "exported_run": exported["id"]}, indent=2))


if __name__ == "__main__":
    main()
