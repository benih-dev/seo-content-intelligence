from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from seoci.db import Base


def now():
    return datetime.now(timezone.utc).isoformat()


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))


class Project(Identity, Base):
    __tablename__ = "projects"
    name: Mapped[str]
    domain: Mapped[str]
    niche: Mapped[str]
    audience: Mapped[str]
    language: Mapped[str] = mapped_column(default="id")
    country: Mapped[str] = mapped_column(default="ID")
    voice_profile: Mapped[str] = mapped_column(default="clear, practical, helpful")
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    publishing: Mapped[dict] = mapped_column(JSON, default=dict)
    business_objective: Mapped[str] = mapped_column(default="Educate readers")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str] = mapped_column(default=now)


class SiteContentItem(Identity, Base):
    __tablename__ = "site_content_items"
    __table_args__ = (UniqueConstraint("project_id", "url"),)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    url: Mapped[str]
    title: Mapped[str] = mapped_column(default="")
    slug: Mapped[str] = mapped_column(default="")
    status: Mapped[str] = mapped_column(default="published")
    last_seen_at: Mapped[str] = mapped_column(default=now)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class WorkflowRun(Identity, Base):
    __tablename__ = "workflow_runs"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    mode: Mapped[str]
    primary_keyword: Mapped[str]
    locale: Mapped[str]
    state: Mapped[str] = mapped_column(default="draft")
    idempotency_key: Mapped[str | None] = mapped_column(unique=True)
    request_fingerprint: Mapped[str] = mapped_column(default="")
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    resume_state: Mapped[str | None]
    revision_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)


class Versioned(Identity):
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(default=1)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(default=now)


class StageArtifact(Versioned, Base):
    __tablename__ = "stage_artifacts"
    __table_args__ = (UniqueConstraint("run_id", "stage", "version"),)
    stage: Mapped[str]


class KeywordRecord(Versioned, Base):
    __tablename__ = "keyword_records"
    keyword: Mapped[str]
    locale: Mapped[str]
    intent: Mapped[str]
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)


class KeywordMetricSnapshot(Identity, Base):
    __tablename__ = "keyword_metric_snapshots"
    keyword_id: Mapped[str] = mapped_column(ForeignKey("keyword_records.id", ondelete="CASCADE"))
    provider: Mapped[str]
    metric_type: Mapped[str]
    value: Mapped[float | None] = mapped_column(Float)
    period: Mapped[str]
    geo: Mapped[str]
    captured_at: Mapped[str] = mapped_column(default=now)


class SERPSnapshot(Versioned, Base):
    __tablename__ = "serp_snapshots"
    query: Mapped[str]
    locale: Mapped[str]
    provider: Mapped[str]


class SERPResult(Identity, Base):
    __tablename__ = "serp_results"
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("serp_snapshots.id", ondelete="CASCADE"))
    rank: Mapped[int]
    url: Mapped[str]
    title: Mapped[str]
    snippet: Mapped[str] = mapped_column(Text)


class ContentBrief(Versioned, Base):
    __tablename__ = "content_briefs"
    __table_args__ = (UniqueConstraint("run_id", "version"),)
    status: Mapped[str] = mapped_column(default="draft")


class ResearchSource(Versioned, Base):
    __tablename__ = "research_sources"
    url: Mapped[str]
    title: Mapped[str]
    publisher: Mapped[str]
    published_at: Mapped[str | None]
    retrieved_at: Mapped[str] = mapped_column(default=now)
    source_type: Mapped[str] = mapped_column(default="web")


class EvidenceItem(Versioned, Base):
    __tablename__ = "evidence_items"
    source_id: Mapped[str] = mapped_column(ForeignKey("research_sources.id", ondelete="CASCADE"))
    claim: Mapped[str] = mapped_column(Text)
    supporting_note: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    review_status: Mapped[str] = mapped_column(default="needs_verification")


class ArticleDraft(Versioned, Base):
    __tablename__ = "article_drafts"
    __table_args__ = (UniqueConstraint("run_id", "version"),)
    body_md: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(default="draft")


class QAReview(Versioned, Base):
    __tablename__ = "qa_reviews"
    draft_id: Mapped[str] = mapped_column(ForeignKey("article_drafts.id", ondelete="CASCADE"))


class ArtifactFile(Versioned, Base):
    __tablename__ = "artifact_files"
    artifact_type: Mapped[str]
    storage_uri: Mapped[str]
    checksum: Mapped[str]


class ApprovalEvent(Versioned, Base):
    __tablename__ = "approval_events"
    stage: Mapped[str]
    actor_id: Mapped[str] = mapped_column(default="user")
    decision: Mapped[str]
    comment: Mapped[str] = mapped_column(default="")


class AuditEvent(Versioned, Base):
    __tablename__ = "audit_events"
    actor: Mapped[str]
    action: Mapped[str]


class Job(Identity, Base):
    __tablename__ = "jobs"
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(default="pending", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=now)
    started_at: Mapped[str | None]
    heartbeat_at: Mapped[str | None]


class ResponseCache(Identity, Base):
    __tablename__ = "response_cache"
    key: Mapped[str] = mapped_column(unique=True)
    data: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[float]
