"""Media-job submission.

A single entry point — :func:`submit_media_job` — runs a job according to the
configured ``job_runner``:

    eager    -> run synchronously in the caller's session (tests, simple setups)
    thread   -> run in a background daemon thread with its own DB session
    dramatiq -> enqueue to the Redis-backed Dramatiq worker

The Dramatiq broker and actor are set up lazily so importing this module never
requires Redis to be reachable.
"""

from __future__ import annotations

import threading

from sqlalchemy.orm import Session

from listenflow.core.config import get_settings
from listenflow.workers.media_pipeline import process_media_job


def submit_media_job(db: Session, job_id: str) -> None:
    """Submit ``job_id`` for processing per the configured runner."""
    runner = get_settings().job_runner

    if runner == "eager":
        process_media_job(db, job_id, storage_root=get_settings().storage_root)
    elif runner == "dramatiq":
        run_media_job.send(job_id)
    else:  # "thread" (default)
        thread = threading.Thread(
            target=_run_in_new_session, args=(job_id,), daemon=True
        )
        thread.start()


def _run_in_new_session(job_id: str) -> None:
    from listenflow.db import get_session_factory

    session_factory = get_session_factory()
    db = session_factory()
    try:
        process_media_job(db, job_id, storage_root=get_settings().storage_root)
    finally:
        db.close()


# ── Dramatiq actor ─────────────────────────────────────────────────────
#
# Run the worker in production with:
#     dramatiq listenflow.workers.tasks
#
# Declaring an actor requires a broker. A RedisBroker does not open a
# connection at construction time, so configuring it on import is safe even
# when Redis is not running and even in eager/thread modes.

try:  # pragma: no cover - exercised only with a running Redis worker
    import dramatiq
    from dramatiq.brokers.redis import RedisBroker

    dramatiq.set_broker(RedisBroker(url=get_settings().redis_url))  # type: ignore[no-untyped-call]

    @dramatiq.actor(max_retries=2)
    def run_media_job(job_id: str) -> None:
        _run_in_new_session(job_id)

except ImportError:  # pragma: no cover - dramatiq always installed in practice

    def run_media_job(job_id: str) -> None:  # type: ignore[misc]
        raise RuntimeError("dramatiq is not installed; cannot enqueue media jobs.")
