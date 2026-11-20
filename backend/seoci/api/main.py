import difflib
import hashlib
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from seoci.api.schemas import (ApprovalInput, DraftInput, InventoryInput, ProjectInput, RunInput,
                               SitemapInput)
from seoci.db import Session, init_db
from seoci.export import render_md, row_dict
from seoci.models import (ApprovalEvent, ArticleDraft, ArtifactFile, AuditEvent, ContentBrief, EvidenceItem,
                          Job, KeywordRecord, Project, QAReview, ResearchSource, SERPSnapshot,
                          SiteContentItem, StageArtifact, WorkflowRun)
from seoci.pipeline.graph import latest
from seoci.pipeline.state import transition
from seoci.providers.llm import Brief
from seoci.providers.sitemap import import_sitemap


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="SEO Content Intelligence", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"], allow_headers=["*"])


def database():
    with Session() as db:
        yield db


def get_or_404(db, cls, ident):
    row = db.get(cls, ident)
    if not row:
        raise HTTPException(404, f"{cls.__name__} not found")
    return row


def lock_run(db, ident):
    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
        return get_or_404(db, WorkflowRun, ident)
    row = db.scalar(select(WorkflowRun).where(WorkflowRun.id == ident).with_for_update())
    if not row:
        raise HTTPException(404, "Run not found")
    return row


def idle(db, run):
    if db.scalar(select(Job.id).where(Job.run_id == run.id, Job.status.in_(["pending", "running"]))):
        raise HTTPException(409, "Run has an active job; wait for completion")


def enqueue(db, run, payload=None):
    job = Job(run_id=run.id, payload=payload or {})
    db.add(job)
    db.flush()
    return job


@app.get("/api/health")
def health(db=Depends(database)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "pipeline": "separate-worker"}


@app.get("/api/projects")
def projects(db=Depends(database)):
    return [row_dict(x) for x in db.scalars(select(Project).order_by(Project.created_at))]


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectInput, db=Depends(database)):
    row = Project(**body.model_dump())
    db.add(row)
    db.commit()
    return row_dict(row)


@app.get("/api/projects/{project_id}")
def project(project_id: str, db=Depends(database)):
    return row_dict(get_or_404(db, Project, project_id))


@app.put("/api/projects/{project_id}")
def update_project(project_id: str, body: ProjectInput, db=Depends(database)):
    row = get_or_404(db, Project, project_id)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    row.version += 1
    db.commit()
    return row_dict(row)


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: str, db=Depends(database)):
    row = get_or_404(db, Project, project_id)
    runs = list(db.scalars(select(WorkflowRun.id).where(WorkflowRun.project_id == project_id)))
    if runs and db.scalar(select(Job.id).where(Job.run_id.in_(runs), Job.status.in_(["pending", "running"]))):
        raise HTTPException(409, "Cannot delete a project with active jobs")
    db.delete(row)
    db.commit()


@app.get("/api/projects/{project_id}/content-items")
def content_items(project_id: str, db=Depends(database)):
    get_or_404(db, Project, project_id)
    return [row_dict(x) for x in db.scalars(select(SiteContentItem).where(SiteContentItem.project_id == project_id))]


@app.post("/api/projects/{project_id}/content-items")
def add_items(project_id: str, body: InventoryInput, db=Depends(database)):
    p = get_or_404(db, Project, project_id)
    items, failures = [], []
    for item in body.items:
        parsed = urlparse(item.url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname != urlparse(p.domain).hostname:
            failures.append({"url": item.url, "error": "URL must belong to project domain"})
            continue
        row = db.scalar(select(SiteContentItem).where(SiteContentItem.project_id == project_id, SiteContentItem.url == item.url))
        if not row:
            row = SiteContentItem(project_id=project_id, **{**item.model_dump(), "slug": item.slug or parsed.path.strip("/")})
            db.add(row)
        else:
            for key, value in item.model_dump().items():
                setattr(row, key, value)
        db.flush()
        items.append(row_dict(row))
    db.commit()
    return {"items": items, "failures": failures}


@app.post("/api/projects/{project_id}/sitemap", status_code=202)
def sitemap(project_id: str, body: SitemapInput, db=Depends(database)):
    p = get_or_404(db, Project, project_id)
    # Import is bounded connector work; article generation always stays in the worker.
    result = import_sitemap(body.url, p.domain)
    imported = add_items(project_id, InventoryInput(items=result["items"]), db)
    imported["failures"] += result["failures"]
    return imported


@app.get("/api/runs")
def runs(project_id: str | None = None, db=Depends(database)):
    query = select(WorkflowRun).order_by(WorkflowRun.created_at.desc())
    if project_id:
        query = query.where(WorkflowRun.project_id == project_id)
    return [row_dict(x) for x in db.scalars(query)]


@app.post("/api/runs", status_code=201)
def create_run(body: RunInput, idempotency_key: str | None = Header(default=None), db=Depends(database)):
    fingerprint = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    def existing():
        row = db.scalar(select(WorkflowRun).where(WorkflowRun.idempotency_key == idempotency_key))
        if row and row.request_fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency-Key was already used with different input")
        return row
    if idempotency_key and (row := existing()):
        return row_dict(row)
    project = get_or_404(db, Project, body.project_id)
    locale = body.locale or f"{project.language}-{project.country}"
    if "-" not in locale or len(locale.split("-")) != 2:
        raise HTTPException(422, "locale must be language-COUNTRY")
    row = WorkflowRun(project_id=body.project_id, mode=body.mode, primary_keyword=body.primary_keyword,
                      locale=locale, idempotency_key=idempotency_key, request_fingerprint=fingerprint)
    db.add(row)
    try:
        db.flush()
        transition(db, row, "ready_for_research", actor="user", reason="Run created")
        enqueue(db, row)
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key and (row := existing()):
            return row_dict(row)
        raise
    return row_dict(row)


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str, db=Depends(database)):
    run = get_or_404(db, WorkflowRun, run_id)
    def rows(cls):
        return [row_dict(x) for x in db.scalars(select(cls).where(cls.run_id == run.id).order_by(cls.created_at))]
    audit = rows(AuditEvent)
    usage = [x["data"] for x in audit if x["action"] == "llm_usage"]
    return {**row_dict(run), "artifacts": rows(StageArtifact), "keywords": rows(KeywordRecord),
            "serp_snapshots": rows(SERPSnapshot), "briefs": rows(ContentBrief), "sources": rows(ResearchSource),
            "evidence": rows(EvidenceItem), "drafts": rows(ArticleDraft), "qa_reviews": rows(QAReview),
            "approvals": rows(ApprovalEvent), "audit": audit, "jobs": [row_dict(x) for x in db.scalars(select(Job).where(Job.run_id == run.id))],
            "usage": {"calls": usage, "cost_usd": sum(x.get("cost_usd", 0) for x in usage),
                      "tokens": sum(x.get("prompt_tokens", 0) + x.get("completion_tokens", 0) for x in usage)},
            "exports": [x.artifact_type for x in db.scalars(select(ArtifactFile).where(ArtifactFile.run_id == run.id))]}


@app.post("/api/runs/{run_id}/approve", status_code=202)
def approve(run_id: str, body: ApprovalInput, db=Depends(database)):
    run = lock_run(db, run_id)
    idle(db, run)
    if run.state != body.stage + "_review":
        raise HTTPException(409, "Approval does not match the current review gate")
    if body.decision == "request_revision" and body.stage != "final":
        raise HTTPException(422, "Edit keyword/brief in payload and approve; request_revision is for final review")
    if body.stage == "keyword":
        keyword = body.payload.get("keyword", run.primary_keyword)
        if not db.scalar(select(KeywordRecord.id).where(KeywordRecord.run_id == run_id, KeywordRecord.keyword == keyword)):
            raise HTTPException(422, "Select an existing shortlist keyword")
    if body.stage == "brief":
        try:
            Brief.model_validate({**latest(db, ContentBrief, run_id).data, **body.payload.get("edits", {})})
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    if body.stage == "final" and body.decision == "approve":
        qa = latest(db, QAReview, run_id)
        if qa.data.get("expert_review_required") and not (body.payload.get("expert_reviewed") is True and body.comment.strip()):
            raise HTTPException(409, "Expert review required: expert_reviewed=true and reviewer comment required")
    row = ApprovalEvent(run_id=run_id, stage=body.stage, decision=body.decision, comment=body.comment, data=body.payload)
    db.add(row)
    job = enqueue(db, run, {"approval": body.model_dump()})
    db.commit()
    return {"run_id": run_id, "job_id": job.id, "state": run.state, "queued": True}


@app.put("/api/runs/{run_id}/draft", status_code=202)
def edit_draft(run_id: str, body: DraftInput, db=Depends(database)):
    run = lock_run(db, run_id)
    idle(db, run)
    if run.state not in {"final_review", "blocked"}:
        raise HTTPException(409, "Draft can be edited at final_review or blocked")
    old = latest(db, ArticleDraft, run_id)
    if not old:
        raise HTTPException(409, "No draft exists")
    if run.state == "blocked":
        run.resume_state = "revision_required"
        transition(db, run, "resumed", actor="user", reason="Manual takeover")
    transition(db, run, "revision_required", actor="user", reason="Manual draft edit")
    draft = ArticleDraft(run_id=run_id, version=old.version + 1, body_md=body.body_md,
                         body_html=render_md(body.body_md), metadata_json=body.metadata_json or old.metadata_json,
                         data={"change_log": "Manual edit"})
    db.add(draft)
    db.flush()
    transition(db, run, "qa", actor="user", reason="Recheck manually edited draft", artifact_ref=draft.id)
    job = enqueue(db, run, {"kind": "manual_qa"})
    db.commit()
    return {"draft_id": draft.id, "version": draft.version, "job_id": job.id, "state": run.state}


@app.post("/api/runs/{run_id}/retry", status_code=202)
def retry_run(run_id: str, db=Depends(database)):
    run = lock_run(db, run_id)
    idle(db, run)
    if run.state not in {"failed", "paused", "needs_human_research"}:
        raise HTTPException(409, "Only failed/paused/research-blocked runs can retry; edit blocked drafts")
    failed = db.scalar(select(Job).where(Job.run_id == run_id, Job.status == "failed").order_by(Job.created_at.desc()))
    if not run.resume_state:
        raise HTTPException(409, "No retry checkpoint; provide research manually in a new run")
    transition(db, run, "resumed", actor="user", reason="Retry requested")
    transition(db, run, run.resume_state, reason="Restore last valid stage")
    run.error = None
    job = enqueue(db, run, failed.payload if failed else {})
    db.commit()
    return {"run_id": run_id, "job_id": job.id, "state": run.state}


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str, db=Depends(database)):
    run = lock_run(db, run_id)
    if db.scalar(select(Job.id).where(Job.run_id == run_id, Job.status == "running")):
        raise HTTPException(409, "Wait for the active stage job before cancelling")
    if run.state not in {"draft", "ready_for_research", "keyword_review", "brief_review", "failed", "blocked", "paused", "needs_human_research"}:
        raise HTTPException(409, "Run cannot be cancelled in its current state")
    transition(db, run, "cancelled", actor="user", reason="User cancelled")
    for job in db.scalars(select(Job).where(Job.run_id == run_id, Job.status == "pending")):
        job.status = "cancelled"
    db.commit()
    return {"run_id": run_id, "state": run.state}


@app.get("/api/runs/{run_id}/export/{fmt}")
def download(run_id: str, fmt: str, db=Depends(database)):
    run = get_or_404(db, WorkflowRun, run_id)
    if fmt not in {"md", "html", "json"}:
        raise HTTPException(404, "Unknown export format")
    if run.state not in {"article_ready", "exported"}:
        raise HTTPException(409, "Final approval required")
    artifact = db.scalar(select(ArtifactFile).where(ArtifactFile.run_id == run_id, ArtifactFile.artifact_type == fmt))
    if not artifact:
        raise HTTPException(409, "Export is still being prepared by worker")
    return Response(artifact.data["content"], media_type={"md": "text/markdown", "html": "text/html", "json": "application/json"}[fmt],
                    headers={"Content-Disposition": f'attachment; filename="article.{fmt}"'})


@app.get("/api/runs/{run_id}/drafts/diff")
def diff(run_id: str, a: int, b: int, db=Depends(database)):
    get_or_404(db, WorkflowRun, run_id)
    def version(v):
        row = db.scalar(select(ArticleDraft).where(ArticleDraft.run_id == run_id, ArticleDraft.version == v))
        if not row:
            raise HTTPException(404, "Draft version not found")
        return row.body_md
    return {"a": a, "b": b, "diff": "\n".join(difflib.unified_diff(version(a).splitlines(), version(b).splitlines(), fromfile=f"v{a}", tofile=f"v{b}", lineterm=""))}
