from datetime import datetime, timedelta, timezone
from threading import Event

from sqlalchemy import select

from seoci.db import Session
from seoci.models import Job
from seoci.worker import claim_job
from tests.conftest import new_run


def test_old_start_does_not_steal_live_lease(client, project):
    new_run(client, project)
    job_id = claim_job()
    with Session() as db:
        job = db.get(Job, job_id)
        job.started_at = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
        db.commit()
    assert claim_job() is None
    with Session() as db:
        assert db.scalar(select(Job.attempts).where(Job.id == job_id)) == 1


def test_expired_orphan_is_reclaimed(client, project):
    new_run(client, project)
    job_id = claim_job()
    with Session() as db:
        job = db.get(Job, job_id)
        job.heartbeat_at = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
        db.commit()
    assert claim_job() == job_id


def test_worker_refreshes_lease_during_execution(client, project, monkeypatch):
    from seoci import worker
    new_run(client, project)
    monkeypatch.setattr(worker, "HEARTBEAT_SECONDS", .01)
    def execute(*args):
        with Session() as db:
            job = db.scalar(select(Job).where(Job.status == "running"))
            job_id = job.id
            old = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
            job.heartbeat_at = old
            db.commit()
        refreshed = False
        for _ in range(100):
            Event().wait(.01)
            with Session() as db:
                if db.get(Job, job_id).heartbeat_at != old:
                    refreshed = True
                    break
        assert refreshed
        assert claim_job() is None
    monkeypatch.setattr(worker, "execute", execute)
    assert worker.work_once()
    with Session() as db:
        assert db.scalar(select(Job.status)) == "done"
