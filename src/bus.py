"""
Typed async pub/sub event bus. All inter-module communication passes through here.
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
Handler = Callable[[Any], Coroutine[Any, Any, None]]


@dataclass
class Event:
    source: str
    timestamp: float


_subscribers: dict[type, list[Handler]] = defaultdict(list)
_queue: asyncio.Queue | None = None


def get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


def subscribe(event_type: Type[T], handler: Handler) -> None:
    _subscribers[event_type].append(handler)
    logger.debug("subscribed %s -> %s", event_type.__name__, handler.__qualname__)


async def publish(event: Event) -> None:
    await get_queue().put(event)


async def run() -> None:
    """Drain the event queue and dispatch to subscribers. Run as a long-lived task."""
    q = get_queue()
    logger.info("event bus running")
    while True:
        event = await q.get()
        handlers = _subscribers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception("handler %s raised on %s", handler.__qualname__, event)
        q.task_done()
