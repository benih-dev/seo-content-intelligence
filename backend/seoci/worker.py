import argparse
import logging
import signal
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from seoci.config import settings
from seoci.db import Session, init_db
from seoci.models import AuditEvent, Job, WorkflowRun, now
from seoci.pipeline.graph import execute
from seoci.pipeline.state import transition

log = logging.getLogger("seoci.worker")


def claim_job():
    with Session() as db:
        if db.bind.dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        # A crashed worker's lease can be reclaimed after network calls have timed out.
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        for stale in db.scalars(select(Job).where(Job.status == "running", Job.started_at < cutoff)):
            stale.status = "pending"
        query = select(Job).where(Job.status == "pending").order_by(Job.created_at).limit(1)
        if db.bind.dialect.name != "sqlite":
            query = query.with_for_update(skip_locked=True)
        job = db.scalar(query)
        if not job:
            db.commit()
            return None
        job.status, job.started_at = "running", now()
        job.attempts += 1
        db.commit()
        return job.id


def work_once():
    job_id = claim_job()
    if not job_id:
        return False
    with Session() as db:
        job = db.get(Job, job_id)
        run = db.get(WorkflowRun, job.run_id)
        if run.state == "cancelled":
            job.status = "cancelled"
            db.commit()
            return True
        payload, run_id = job.payload, job.run_id
    try:
        execute(run_id, payload)
        with Session() as db:
            job = db.get(Job, job_id)
            job.status, job.error = "done", None
            db.commit()
    except Exception as exc:
        log.exception("Run %s failed", run_id)
        with Session() as db:
            job = db.get(Job, job_id)
            job.status, job.error = "failed", str(exc)
            run = db.get(WorkflowRun, run_id)
            run.error = str(exc)
            if run.state not in {"cancelled", "exported", "failed", "blocked"}:
                run.resume_state = run.state
                transition(db, run, "failed", reason=str(exc))
            db.add(AuditEvent(run_id=run_id, actor="system", action="job_error", data={"error": str(exc), "type": type(exc).__name__, "attempt": job.attempts}))
            db.commit()
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    init_db()
    if args.once:
        work_once()
        return
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("Worker ready (database queue)")
    while running:
        if not work_once():
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
