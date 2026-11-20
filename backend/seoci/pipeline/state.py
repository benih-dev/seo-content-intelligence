from seoci.models import AuditEvent, now

ALLOWED = {
    "draft": {"ready_for_research", "cancelled"},
    "ready_for_research": {"researching", "cancelled"},
    "researching": {"keyword_review", "failed", "paused"},
    "keyword_review": {"strategy", "paused", "cancelled"},
    "strategy": {"brief_review", "failed", "paused"},
    "brief_review": {"evidence_research", "strategy", "cancelled"},
    "evidence_research": {"drafting", "needs_human_research", "failed"},
    "drafting": {"optimizing", "failed", "paused"},
    "optimizing": {"qa", "drafting"},
    "qa": {"revision_required", "final_review", "blocked"},
    "revision_required": {"drafting", "optimizing", "qa"},
    "final_review": {"article_ready", "revision_required"},
    "article_ready": {"exported", "failed"},
    "failed": {"retry", "resumed", "cancelled"},
    "blocked": {"retry", "resumed", "cancelled"},
    "needs_human_research": {"resumed", "cancelled"},
    "paused": {"resumed", "cancelled"},
    "retry": {"resumed"},
    "exported": set(), "cancelled": set(),
}


def transition(db, run, new_state, actor="system", reason="", artifact_ref=None):
    if run.state == new_state:
        return
    old = run.state
    # resumed is an explicit restoration to the last valid checkpoint stage.
    if old == "resumed":
        allowed = new_state == run.resume_state
    elif new_state == "failed" and old not in {"exported", "cancelled"}:
        allowed = True
    else:
        allowed = new_state in ALLOWED.get(old, set())
    if not allowed:
        raise ValueError(f"Invalid transition {old} -> {new_state}")
    run.state, run.updated_at = new_state, now()
    db.add(AuditEvent(run_id=run.id, actor=actor, action="transition",
                     data={"from": old, "to": new_state, "reason": reason, "artifact_ref": artifact_ref}))
