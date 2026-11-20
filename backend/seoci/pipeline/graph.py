import json
import time
from contextlib import contextmanager
from typing import TypedDict

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import select

from seoci.config import settings
from seoci.db import Session
from seoci.diagnostics import context as diagnostic_context, classify, ProviderFailure, record_event
from seoci.export import build_exports, render_md, row_dict, with_article_h1
from seoci.models import (ApprovalEvent, ArticleDraft, AuditEvent, ContentBrief, EvidenceItem, KeywordMetricSnapshot,
                          Job, KeywordRecord, Project, QAReview, ResearchSource, SERPResult, SERPSnapshot,
                          SiteContentItem, StageArtifact, WorkflowRun, now)
from seoci.pipeline.quality import (annotate_internal_links, available_slug, check_article, opportunity, overlap,
                                    suggest_internal_links, ymyl)
from seoci.pipeline.state import transition
from seoci.providers.keywords import get_keywords
from seoci.providers.llm import Brief, Draft, Intent, QA, SEO, Strategy, get_llm
from seoci.providers.research import ResearchProvider
from seoci.providers.network import active_session
from seoci.providers.serp import get_serp


class State(TypedDict):
    run_id: str


def latest(db, cls, run_id):
    return db.scalar(select(cls).where(cls.run_id == run_id).order_by(cls.version.desc(), cls.created_at.desc()))


def artifact(db, run_id, stage, version=1):
    return db.scalar(select(StageArtifact).where(StageArtifact.run_id == run_id, StageArtifact.stage == stage, StageArtifact.version == version))


def context(db, run):
    p = run.context.get("project") or row_dict(db.get(Project, run.project_id))
    records = list(db.scalars(select(KeywordRecord).where(KeywordRecord.run_id == run.id, KeywordRecord.selected.is_(True))))
    brief = latest(db, ContentBrief, run.id)
    return {"keyword": run.primary_keyword, "language": p["language"], "audience": p["audience"], "domain": p["domain"],
            "niche": p["niche"], "voice_profile": p["voice_profile"], "rules": p["rules"],
            "business_objective": p["business_objective"], "intent": records[0].intent if records else "informational",
            "inventory": [x.url for x in db.scalars(select(SiteContentItem).where(SiteContentItem.project_id == run.project_id))],
            "brief": brief.data if brief else {},
            "sources": [row_dict(x) for x in db.scalars(select(ResearchSource).where(ResearchSource.run_id == run.id))],
            "evidence": [row_dict(x) for x in db.scalars(select(EvidenceItem).where(EvidenceItem.run_id == run.id))]}


def llm_call(db, run, task, schema, extra=None):
    usages = list(db.scalars(select(AuditEvent).where(AuditEvent.run_id == run.id, AuditEvent.action == "llm_usage")))
    spent = sum(x.data.get("cost_usd", 0) for x in usages)
    pending = db.info.setdefault("llm_usage", [])
    spent += sum(data.get("cost_usd", 0) for run_id, data in pending if run_id == run.id)
    if spent >= settings.run_budget_usd:
        raise RuntimeError("Run budget exhausted")
    client = get_llm()
    prompt = json.dumps({**context(db, run), **(extra or {})}, ensure_ascii=False)
    start = time.monotonic()
    try:
        result = client.complete_json(task, prompt, schema)
    finally:
        for usage in client.usage:
            pending.append((run.id, {**usage, "latency_ms": round((time.monotonic()-start)*1000), "prompt_version": "v1"}))
    return result.model_dump()


def stage(name, fn, version_fn=lambda db, run: 1):
    def node(state):
        with Session() as db:
            run = db.get(WorkflowRun, state["run_id"])
            if run.state == "cancelled":
                raise RuntimeError("Run cancelled")
            version = version_fn(db, run)
            if artifact(db, run.id, name, version):
                return {}
            start = time.monotonic()
            token = active_session.set(db)
            diagnostic_token = diagnostic_context.set({**diagnostic_context.get(), "stage": name, "run_id": run.id})
            try:
                data = fn(db, run) or {}
                row = StageArtifact(run_id=run.id, stage=name, version=version, data=data)
                db.add(row)
                db.flush()
                db.add(AuditEvent(run_id=run.id, actor="system", action="stage_complete", data={"stage": name, "artifact_id": row.id, "version": version, "latency_ms": round((time.monotonic()-start)*1000)}))
                for job in db.scalars(select(Job).where(Job.run_id == run.id, Job.status == "running")):
                    job.heartbeat_at = now()
                db.commit()
                record_event(message="Stage completed", duration_ms=round((time.monotonic()-start)*1000))
            except Exception as exc:
                error = {**classify(exc), "stage": name}
                raise ProviderFailure(error) from None
            finally:
                diagnostic_context.reset(diagnostic_token)
                active_session.reset(token)
                usages = db.info.pop("llm_usage", [])
                db.rollback()
                if usages:
                    with Session() as usage_db:
                        usage_db.add_all(AuditEvent(run_id=run_id, actor="system", action="llm_usage", data=data) for run_id, data in usages)
                        usage_db.commit()
        return {}
    return node


def load_context(db, run):
    if not run.context.get("project"):
        project = db.get(Project, run.project_id)
        run.context = {"project": row_dict(project), "project_version": project.version}
    transition(db, run, "researching", reason="Context loaded")
    return run.context


def keyword_research(db, run):
    provider = get_keywords()
    candidates = provider.suggestions(run.primary_keyword, run.locale) if run.mode == "discovery" else [run.primary_keyword]
    metrics = provider.metrics(candidates, run.locale)
    shortlist = []
    inventory = list(db.scalars(select(SiteContentItem).where(SiteContentItem.project_id == run.project_id)))
    for keyword in candidates:
        snapshot = get_serp().search(keyword, run.locale)
        if not snapshot.get("results"):
            raise RuntimeError("Empty SERP response; retry available")
        snap = SERPSnapshot(run_id=run.id, query=keyword, locale=run.locale, provider=snapshot["provider"], data=snapshot)
        db.add(snap)
        db.flush()
        for result in snapshot["results"]:
            db.add(SERPResult(snapshot_id=snap.id, **result))
        intent = llm_call(db, run, "intent", Intent, {"keyword": keyword, "serp": snapshot})
        metric = metrics[keyword]
        score = opportunity(metric, not snapshot.get("mock", False), keyword, run.context["project"], intent["label"])
        record = KeywordRecord(run_id=run.id, keyword=keyword, locale=run.locale, intent=intent["label"],
                               score=score["score"], confidence=score["confidence"], data={"intent": intent, "metrics": metric, "opportunity": score, "serp_snapshot_id": snap.id,
                               "overlap_warnings": overlap(keyword, inventory), "inventory_count": len(inventory),
                               "inventory_missing_metadata": sum(not x.title.strip() for x in inventory)})
        db.add(record)
        db.flush()
        db.add(KeywordMetricSnapshot(keyword_id=record.id, provider=metric["provider"], metric_type="search_volume",
                                     value=metric["volume"], period=metric["period"], geo=metric["locale"]))
        if metric["provider"] == "search_console":
            for name in ("impressions", "clicks", "ctr", "position"):
                db.add(KeywordMetricSnapshot(keyword_id=record.id, provider=metric["provider"], metric_type=name,
                                             value=metric.get(name), period=metric["period"], geo=metric["locale"]))
        shortlist.append({"id": record.id, "keyword": keyword, **record.data})
    transition(db, run, "keyword_review", reason="Shortlist ready; human keyword approval required")
    return {"shortlist": shortlist, "ymyl": ymyl(run.primary_keyword)}


def keyword_review(state):
    decision = interrupt({"stage": "keyword", "message": "Select keyword and confirm intent"})
    with Session() as db:
        run = db.get(WorkflowRun, state["run_id"])
        if run.state != "keyword_review":
            return {}
        payload = decision.get("payload", {})
        chosen = payload.get("keyword", run.primary_keyword)
        record = db.scalar(select(KeywordRecord).where(KeywordRecord.run_id == run.id, KeywordRecord.keyword == chosen))
        if not record:
            raise ValueError("Select a keyword from the shortlist")
        record.selected = True
        record.intent = payload.get("intent", record.intent)
        snapshot = db.get(SERPSnapshot, record.data["serp_snapshot_id"])
        score = opportunity(record.data["metrics"], not snapshot.data.get("mock", False),
                            chosen, run.context["project"], record.intent)
        record.data = {**record.data, "final_intent": record.intent, "opportunity": score}
        record.score, record.confidence = score["score"], score["confidence"]
        run.primary_keyword = chosen
        transition(db, run, "strategy", actor="user", reason="Keyword and final intent approved", artifact_ref=record.id)
        db.commit()
    return {}


def strategy(db, run):
    data = llm_call(db, run, "strategy", Strategy)
    data["overlap_warnings"] = overlap(run.primary_keyword, db.scalars(select(SiteContentItem).where(SiteContentItem.project_id == run.project_id)))
    data["ymyl"] = ymyl(run.primary_keyword)
    data["expert_review_label"] = "Expert review required" if data["ymyl"] else None
    return data


def internal_links(db, run, data):
    inventory = list(db.scalars(select(SiteContentItem).where(SiteContentItem.project_id == run.project_id)))
    links = annotate_internal_links(data.get("internal_links", []), inventory)
    if not links and not data.get("internal_links"):
        topic = " ".join([run.primary_keyword] + [x["heading"] for x in data["outline"]] + data.get("subtopics", []))
        links = suggest_internal_links(inventory, topic)
    return links


def brief(db, run):
    strategy_data = (artifact(db, run.id, "strategy") or StageArtifact(data={})).data
    strategy_view = {k: strategy_data.get(k, "") for k in ("angle", "rationale", "differentiation")}
    data = llm_call(db, run, "brief", Brief, {"strategy": strategy_view})
    for key in ("rationale", "differentiation"):
        data[key] = data.get(key) or strategy_view[key]
    data["internal_links"] = internal_links(db, run, data)
    row = ContentBrief(run_id=run.id, data=data)
    db.add(row)
    db.flush()
    transition(db, run, "brief_review", reason="Brief ready for editing and approval", artifact_ref=row.id)
    return data


def brief_review(state):
    decision = interrupt({"stage": "brief", "message": "Review/edit brief before writing"})
    with Session() as db:
        run = db.get(WorkflowRun, state["run_id"])
        if run.state != "brief_review":
            return {}
        row = latest(db, ContentBrief, run.id)
        edits = decision.get("payload", {}).get("edits")
        if edits:
            data = Brief.model_validate({**row.data, **edits}).model_dump()
            data["internal_links"] = annotate_internal_links(data["internal_links"], db.scalars(
                select(SiteContentItem).where(SiteContentItem.project_id == run.project_id)))
            if data != row.data:
                row = ContentBrief(run_id=run.id, version=row.version + 1, data=data)
                db.add(row)
        row.status = "approved"
        db.flush()
        transition(db, run, "evidence_research", actor="user", reason=f"Brief v{row.version} approved", artifact_ref=row.id)
        db.commit()
    return {}


def evidence_research(db, run):
    ctx = context(db, run)
    sources = ResearchProvider().find_sources(ctx["brief"].get("source_plan", [run.primary_keyword]), run.locale)
    if not sources:
        transition(db, run, "needs_human_research", reason="No sources found")
        return {"sources": []}
    ids = []
    for source in sources:
        row = ResearchSource(run_id=run.id, url=source["url"], title=source["title"], publisher=source["publisher"],
                             published_at=source["published_at"], retrieved_at=source["retrieved_at"], data={"snippet": source["snippet"], "mock": source["mock"]})
        db.add(row)
        db.flush()
        db.add(EvidenceItem(run_id=run.id, source_id=row.id, claim=source["snippet"].removeprefix("<untrusted_source>").removesuffix("</untrusted_source>"),
                             supporting_note=source["snippet"], confidence=.4 if source["mock"] else .6,
                             review_status="needs_verification", data={"url": row.url, "scope": "demo source summary; not fetched or independently verified" if source["mock"] else "source snippet; verify claim context"}))
        ids.append(row.id)
    transition(db, run, "drafting", reason="Evidence ledger collected")
    return {"source_ids": ids, "unresolved": "Sources require editorial verification; mock sources are not topic-specific research" if sources[0]["mock"] else "Verify source context"}


def drafting(db, run):
    if run.state == "revision_required":
        transition(db, run, "drafting", reason="Apply bounded revision")
    old = latest(db, ArticleDraft, run.id)
    version = old.version + 1 if old else 1
    feedback = {"previous_draft": old.body_md if old else None, "revision_instructions": ""}
    if old:
        review = latest(db, QAReview, run.id)
        approval = db.scalar(select(ApprovalEvent).where(
            ApprovalEvent.run_id == run.id, ApprovalEvent.stage == "final",
            ApprovalEvent.decision == "request_revision", ApprovalEvent.created_at >= review.created_at,
        ).order_by(ApprovalEvent.created_at.desc()).limit(1)) if review else None
        feedback.update(reviewer_comment=approval.comment if approval else None,
                        qa_findings=review.data.get("findings", []) if review else [],
                        revision_instructions=approval.comment if approval and approval.created_at >= old.created_at else "",
                        revision_instruction="Revise the previous draft in place. Preserve existing edits and "
                        "sections unless the reviewer comment or QA findings require changing them.")
    data = llm_call(db, run, "revise" if old else "draft", Draft, feedback)
    row = ArticleDraft(run_id=run.id, version=version, body_md=data["body_md"], body_html=render_md(data["body_md"]), data={"change_log": data["change_log"]})
    db.add(row)
    db.flush()
    transition(db, run, "optimizing", reason="Draft saved", artifact_ref=row.id)
    return {"draft_id": row.id, "version": version}


def optimizing(db, run):
    row = latest(db, ArticleDraft, run.id)
    row.metadata_json = {**llm_call(db, run, "seo", SEO, {"body_md": row.body_md}), "primary_keyword": run.primary_keyword, "locale": run.locale}
    ctx = context(db, run)
    row.metadata_json = with_article_h1(row.body_md, {
        **row.metadata_json, "slug": available_slug(row.metadata_json["slug"], ctx["domain"], ctx["inventory"]),
    })
    transition(db, run, "qa", reason="SEO metadata generated", artifact_ref=row.id)
    return row.metadata_json


def qa(db, run):
    row = latest(db, ArticleDraft, run.id)
    ctx = context(db, run)
    publishers = {source["id"]: source["publisher"] for source in ctx["sources"]}
    evidence = [{**x, "url": x["data"].get("url"), "publisher": publishers.get(x["source_id"])} for x in ctx["evidence"]]
    result = check_article(row.body_md, row.metadata_json, evidence, ctx["inventory"], run.primary_keyword, ymyl(run.primary_keyword), project_domain=ctx["domain"])
    review = llm_call(db, run, "qa", QA, {"body_md": row.body_md, "metadata": row.metadata_json})
    result["findings"] += review["findings"]
    result["summary"] = review["summary"]
    result["status"] = "blocked" if any(x.get("severity") == "blocker" for x in result["findings"]) else "needs_revision" if any(x.get("severity") == "major" for x in result["findings"]) else "pass"
    db.add(QAReview(run_id=run.id, draft_id=row.id, version=row.version, data=result))
    human_flags = {"Expert review required", "YMYL sources need human verification"}
    unresolved = [x for x in result["findings"] if x.get("severity") in {"blocker", "major"}
                  and x.get("finding") not in human_flags]
    if unresolved and row.data.get("origin") == "manual":
        transition(db, run, "blocked", reason="Manual draft needs fixes; see QA findings", artifact_ref=row.id)
    elif unresolved and run.revision_count < settings.max_revision_cycles:
        run.revision_count += 1
        transition(db, run, "revision_required", reason="QA requires revision")
    elif unresolved:
        transition(db, run, "blocked", reason="Revision cap reached; manual edit required")
    else:
        transition(db, run, "final_review", reason="QA completed; resolve expert flags at human gate", artifact_ref=row.id)
    return result


def qa_route(state):
    with Session() as db:
        run = db.get(WorkflowRun, state["run_id"])
        return "drafting" if run.state == "revision_required" else "final_review" if run.state == "final_review" else END


def final_review(state):
    decision = interrupt({"stage": "final", "message": "Review article, evidence, QA and approve or request revision"})
    with Session() as db:
        run = db.get(WorkflowRun, state["run_id"])
        if run.state != "final_review":
            return {}
        if decision["decision"] == "request_revision":
            run.revision_count += 1
            transition(db, run, "revision_required", actor="user", reason=decision.get("comment", "User requested revision"))
        else:
            draft = latest(db, ArticleDraft, run.id)
            payload = decision.get("payload", {})
            if payload.get("draft_id") != draft.id or payload.get("draft_version") != draft.version:
                raise ValueError("Reviewed draft is not the latest draft")
            review = latest(db, QAReview, run.id)
            expert = decision.get("payload", {}).get("expert_reviewed", False)
            if review.data["expert_review_required"] and not expert:
                raise ValueError("Expert review required: explicit expert_reviewed acknowledgement missing")
            if expert:
                review.data = {**review.data, "human_resolution": {"expert_reviewed": True, "comment": decision.get("comment", "")}}
            draft = latest(db, ArticleDraft, run.id)
            draft.status = "approved"
            transition(db, run, "article_ready", actor="user", reason="Final article approved", artifact_ref=draft.id)
        db.commit()
    return {}


def final_route(state):
    with Session() as db:
        return "drafting" if db.get(WorkflowRun, state["run_id"]).state == "revision_required" else "article_ready"


def article_ready(db, run):
    return {"state": run.state, "publication": "No automatic publishing"}


def export(db, run):
    build_exports(db, run)
    transition(db, run, "exported", reason="Approved MD/HTML/JSON artifacts stored")
    return {"formats": ["md", "html", "json"]}


def build_graph(checkpointer):
    graph = StateGraph(State)
    for name, fn in [("load_context", load_context), ("keyword_research", keyword_research), ("strategy", strategy),
                     ("brief", brief), ("evidence_research", evidence_research), ("article_ready", article_ready), ("export", export)]:
        graph.add_node(name, stage(name, fn))
    graph.add_node("drafting", stage("drafting", drafting, lambda db, r: r.revision_count + 1))
    for name, fn in [("optimizing", optimizing), ("qa", qa)]:
        graph.add_node(name, stage(name, fn, lambda db, r: latest(db, ArticleDraft, r.id).version))
    for name, fn in [("keyword_review", keyword_review), ("brief_review", brief_review), ("final_review", final_review)]:
        graph.add_node(name, fn)
    path = [START, "load_context", "keyword_research", "keyword_review", "strategy", "brief", "brief_review", "evidence_research"]
    for a, b in zip(path, path[1:]):
        graph.add_edge(a, b)
    graph.add_conditional_edges("evidence_research", lambda state: evidence_route(state))
    graph.add_edge("drafting", "optimizing")
    graph.add_edge("optimizing", "qa")
    graph.add_conditional_edges("qa", qa_route)
    graph.add_conditional_edges("final_review", final_route)
    graph.add_edge("article_ready", "export")
    graph.add_edge("export", END)
    return graph.compile(checkpointer=checkpointer)


def evidence_route(state):
    with Session() as db:
        return "drafting" if db.get(WorkflowRun, state["run_id"]).state == "drafting" else END


@contextmanager
def saved_graph():
    url = settings.database_url
    if url.startswith("sqlite"):
        path = url.split("///", 1)[1] + ".checkpoints"
        with SqliteSaver.from_conn_string(path) as saver:
            yield build_graph(saver)
    else:
        with PostgresSaver.from_conn_string(url.replace("postgresql+psycopg://", "postgresql://")) as saver:
            saver.setup()
            yield build_graph(saver)


def execute(run_id, payload):
    config = {"configurable": {"thread_id": run_id}, "recursion_limit": 100}
    with saved_graph() as graph:
        if payload.get("kind") == "manual_qa":
            graph.update_state(config, {"run_id": run_id}, as_node="optimizing")
            graph.invoke(None, config)
        elif payload.get("approval"):
            graph.invoke(Command(resume=payload["approval"]), config)
        else:
            snapshot = graph.get_state(config)
            graph.invoke(None if snapshot.values else {"run_id": run_id}, config)
