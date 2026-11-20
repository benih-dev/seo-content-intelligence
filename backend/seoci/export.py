import hashlib
import html
import json

from markdown_it import MarkdownIt
from sqlalchemy import select

from seoci.models import (ArticleDraft, ArtifactFile, ContentBrief, EvidenceItem, QAReview,
                          ResearchSource, WorkflowRun)


def markdown_headings(body):
    tokens = MarkdownIt("commonmark", {"html": False}).parse(body)
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            text = "".join(
                " " if child.type in {"softbreak", "hardbreak"} else child.content
                for child in tokens[i + 1].children or []
                if child.type in {"text", "code_inline", "image", "softbreak", "hardbreak"}
            )
            yield token.map[0] + 1, int(token.tag[1:]), text


def with_article_h1(body, metadata):
    h1 = next((text for _, level, text in markdown_headings(body) if level == 1), "")
    return {**metadata, "h1": h1}


def render_md(body):
    return MarkdownIt("commonmark", {"html": False}).enable("table").render(body)


def row_dict(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def build_exports(db, run: WorkflowRun):
    if run.state not in {"article_ready", "exported"}:
        raise ValueError("Final approval required")
    drafts = list(db.scalars(select(ArticleDraft).where(ArticleDraft.run_id == run.id).order_by(ArticleDraft.version)))
    draft = drafts[-1]
    def rows(cls):
        return [row_dict(x) for x in db.scalars(select(cls).where(cls.run_id == run.id))]
    package = {"schema_version": "1.0", "id": run.id, "metadata": draft.metadata_json,
               "brief": rows(ContentBrief), "evidence_ledger": rows(EvidenceItem), "sources": rows(ResearchSource),
               "qa_report": rows(QAReview), "versions": [row_dict(x) for x in drafts],
               "article": {"id": draft.id, "body_md": draft.body_md, "body_html": render_md(draft.body_md)}}
    outputs = {"md": draft.body_md, "html": "<!doctype html><html><head><meta charset=\"utf-8\"><title>" + html.escape(draft.metadata_json.get("title", "Article")) + "</title></head><body>" + render_md(draft.body_md) + "</body></html>",
               "json": json.dumps(package, ensure_ascii=False, indent=2)}
    for fmt, content in outputs.items():
        existing = db.scalar(select(ArtifactFile).where(ArtifactFile.run_id == run.id, ArtifactFile.artifact_type == fmt))
        if not existing:
            db.add(ArtifactFile(run_id=run.id, artifact_type=fmt, storage_uri=f"db://{run.id}/{fmt}",
                                checksum=hashlib.sha256(content.encode()).hexdigest(), data={"content": content}))
    return outputs
