"""Live curl acceptance transcript; start API and worker first."""
import json
import shlex
import subprocess
import time


def curl(path, body=None, headers=None, echo=True, output=None):
    command = ["curl", "-fsS", "http://127.0.0.1:8000" + path]
    if body is not None:
        command += ["-H", "Content-Type: application/json", "-d", json.dumps(body, ensure_ascii=False)]
    for header in headers or []:
        command += ["-H", header]
    if output:
        command += ["-o", output]
    if echo:
        print("$ " + shlex.join(command), flush=True)
    result = subprocess.check_output(command, text=True)
    if echo and result:
        print(result, flush=True)
    return json.loads(result) if result else None


def wait_for(run_id, state):
    for _ in range(200):
        run = curl(f"/api/runs/{run_id}", echo=False)
        if run["state"] in {"failed", "blocked"}:
            raise RuntimeError(run["error"] or str(run["qa_reviews"]))
        if run["state"] == state and not any(x["status"] in {"pending", "running"} for x in run["jobs"]):
            print(f"# worker reached {state}", flush=True)
            return run
        time.sleep(.1)
    raise TimeoutError(state)


def main():
    curl("/api/health")
    project = curl("/api/projects", {"name": "Kebun Balkon Demo", "domain": "https://example.com", "niche": "berkebun di ruang terbatas", "audience": "pemula yang tinggal di apartemen", "language": "id", "country": "ID", "voice_profile": "ramah, jelas, praktis"})
    run = curl("/api/runs", {"project_id": project["id"], "mode": "selected", "primary_keyword": "berkebun di balkon"}, ["Idempotency-Key: live-demo-balcony"])
    ident = run["id"]
    wait_for(ident, "keyword_review")
    curl(f"/api/runs/{ident}/approve", {"stage": "keyword", "payload": {"keyword": "berkebun di balkon", "intent": "informational"}, "comment": "Keyword relevan untuk pembaca apartemen"})
    wait_for(ident, "brief_review")
    curl(f"/api/runs/{ident}/approve", {"stage": "brief", "comment": "Struktur dan cakupan disetujui"})
    reviewed = wait_for(ident, "final_review")["drafts"][-1]
    curl(f"/api/runs/{ident}/approve", {"stage": "final", "payload": {"draft_id": reviewed["id"], "draft_version": reviewed["version"]}, "comment": "Contoh demo dan batasan sumber telah diperiksa"})
    final = wait_for(ident, "exported")
    curl(f"/api/runs/{ident}/export/md", output="data/demo-article.md")
    print("$ head -n 30 data/demo-article.md", flush=True)
    print(subprocess.check_output(["head", "-n", "30", "data/demo-article.md"], text=True), flush=True)
    print(f"$ curl -fsS http://127.0.0.1:8000/api/runs/{ident} | python -c '<extract audit transitions>'", flush=True)
    print(json.dumps([{"at": x["created_at"], "actor": x["actor"], **x["data"]} for x in final["audit"] if x["action"] == "transition"], ensure_ascii=False, indent=2), flush=True)
    print(f"RUN_ID={ident}", flush=True)


if __name__ == "__main__":
    main()
