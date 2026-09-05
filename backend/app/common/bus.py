"""In-process event bus bridging the relay thread to asyncio SSE streams
(research R5): threads publish; open streams subscribe per user and await
with a timeout so keep-alives interleave with deliveries."""

from __future__ import annotations

import asyncio
import json
import threading
from contextlib import suppress
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BusMessage:
    user_id: str
    payload: dict[str, Any]


class NotificationBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queues: dict[str, set[asyncio.Queue[BusMessage]]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the running asyncio loop (called once at app startup)."""
        self._loop = loop

    def subscribe(self, user_id: str) -> asyncio.Queue[BusMessage]:
        queue: asyncio.Queue[BusMessage] = asyncio.Queue(maxsize=64)
        with self._lock:
            self._queues.setdefault(user_id, set()).add(queue)
        return queue

    def unsubscribe(self, user_id: str, queue: asyncio.Queue[BusMessage]) -> None:
        with self._lock:
            subscribers = self._queues.get(user_id)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    self._queues.pop(user_id, None)

    def publish_threadsafe(self, user_id: str, payload: dict[str, Any]) -> None:
        """Safe to call from the relay thread: schedules fan-out on the loop."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        message = BusMessage(user_id=user_id, payload=payload)

        def _fanout() -> None:
            with self._lock:
                targets = list(self._queues.get(user_id, ()))
            for queue in targets:
                with suppress(asyncio.QueueFull):
                    queue.put_nowait(message)

        loop.call_soon_threadsafe(_fanout)

    def subscriber_count(self, user_id: str) -> int:
        with self._lock:
            return len(self._queues.get(user_id, ()))

    async def wait_for_message(
        self, queue: asyncio.Queue[BusMessage], timeout: float
    ) -> BusMessage | None:
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except TimeoutError:
            return None


def encode_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


bus = NotificationBus()
