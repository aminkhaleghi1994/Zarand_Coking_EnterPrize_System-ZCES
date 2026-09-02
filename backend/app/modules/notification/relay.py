"""Outbox relay (US2, research R2): a lifespan-managed daemon thread that
polls the outbox, claims pending events with row locking, delivers them and
pushes each new notification onto the in-process bus for live SSE streams.

- poll every RELAY_POLL_SECONDS (default 2s), claim ≤ RELAY_BATCH_SIZE;
- on start, orphaned ``processing`` rows are re-claimed (at-least-once —
  the exactly-once unique keeps the effect idempotent);
- each event is delivered and committed on its own so one failure never
  blocks the rest; failures never raise into business transactions (§20);
- tests drive ``deliver_event`` directly; latency tests start their own
  worker with a short poll interval.
"""

from __future__ import annotations

import logging
import threading

from app.common.bus import bus
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.modules.notification import repository, service
from app.modules.notification.models import EventOutbox
from app.modules.notification.schemas import NotificationOut

logger = logging.getLogger("zces.notification.relay")


def _publish_delivered(session, event: EventOutbox) -> None:  # type: ignore[no-untyped-def]
    """Fan the just-delivered rows out to open SSE streams (research R5)."""
    for row in repository.notifications_for_event(session, event.id):
        bus.publish_threadsafe(
            str(row.user_id),
            NotificationOut.model_validate(row, from_attributes=True).model_dump(mode="json"),
        )


class RelayWorker:
    """Polling worker; one instance per process (lifespan-managed)."""

    def __init__(self, poll_seconds: float | None = None, batch_size: int | None = None) -> None:
        settings = get_settings()
        self._poll_seconds = (
            poll_seconds if poll_seconds is not None else settings.RELAY_POLL_SECONDS
        )
        self._batch_size = batch_size if batch_size is not None else settings.RELAY_BATCH_SIZE
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="notification-relay", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None

    def _run(self) -> None:
        logger.info(
            "notification relay started (poll=%.2fs, batch=%d)",
            self._poll_seconds,
            self._batch_size,
        )
        self._reclaim_orphans()
        while not self._stop.is_set():
            self._poll_once()
            self._stop.wait(self._poll_seconds)
        logger.info("notification relay stopped")

    def _reclaim_orphans(self) -> None:
        try:
            with get_session_factory()() as session:
                reclaimed = repository.reclaim_processing(session)
                session.commit()
            if reclaimed:
                logger.info("relay re-claimed %d orphaned processing events", reclaimed)
        except Exception:  # noqa: BLE001 — the relay must never crash the app
            logger.exception("relay orphan re-claim failed; will retry next poll")

    def _poll_once(self) -> None:
        try:
            with get_session_factory()() as session:
                claimed = repository.claim_pending(session, limit=self._batch_size)
                if not claimed:
                    session.rollback()
                    return
                for event, status in service.deliver_claimed_batch(session, claimed):
                    session.commit()
                    if status == "delivered":
                        _publish_delivered(session, event)
        except Exception:  # noqa: BLE001 — keep polling; log and continue
            logger.exception("relay poll cycle failed")


def start_relay() -> RelayWorker | None:
    """Lifespan entry: start the polling worker when enabled (settings)."""
    if not get_settings().RELAY_ENABLED:
        return None
    worker = RelayWorker()
    worker.start()
    return worker


def stop_relay(worker: RelayWorker | None) -> None:
    if worker is not None:
        worker.stop()
