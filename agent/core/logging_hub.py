"""Event logging and live log streaming.

Two responsibilities:

  - ``log_event`` writes a JSON Lines record to ``/logs/YYYY-MM-DD.log`` and
    publishes the same line to in-memory subscribers (the SSE endpoint).
  - ``LogStreamHub`` is the publish/subscribe primitive used by the
    ``/logs/stream`` HTTP endpoint to fan out events to connected dashboards.

A module-level ``LOG_STREAM_HUB`` instance is exposed for now to preserve the
original app.py call pattern. Later refactor steps will inject the hub
explicitly into the HTTP server, runner, and CLI; once no module imports
``LOG_STREAM_HUB`` directly, the global can be removed.
"""

import json
import os
import threading
from datetime import datetime
from queue import Queue
from typing import Any, Dict, List

from core.config import LOGS_DIR


class LogStreamHub:
    """Thread-safe pub/sub fan-out for log lines.

    Each subscriber gets its own ``Queue``; ``publish`` pushes the message
    to every subscriber's queue under a single lock. The SSE handler pops
    from its queue with a timeout so it can emit keep-alive comments.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: List[Queue[str]] = []

    def subscribe(self) -> Queue[str]:
        queue: Queue[str] = Queue()
        with self._lock:
            self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: Queue[str]) -> None:
        with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    def publish(self, message: str) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            queue.put(message)


# Module-level instance — kept for backwards compatibility with the original
# global pattern. Downstream commits will inject the hub explicitly and we
# will be able to retire this global.
LOG_STREAM_HUB: LogStreamHub = LogStreamHub()


def log_event(event_type: str, payload: Dict[str, Any]) -> None:
    """Append a JSON Lines record to today's log file and publish it live.

    The on-disk format and the wire format are the same line, so dashboards
    consuming ``/logs/stream`` see the exact same payload as a tail of the
    file. Errors during the file write are not caught here — the original
    behaviour was to fail loudly, and we preserve it.
    """
    import sys
    print(f"[LOG_EVENT] {event_type} -> LOG_STREAM_HUB id={id(LOG_STREAM_HUB)} subscribers={len(LOG_STREAM_HUB._subscribers)}", flush=True, file=sys.stderr)   
    os.makedirs(LOGS_DIR, exist_ok=True)
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    date_str = datetime.utcnow().date().isoformat()
    log_path = os.path.join(LOGS_DIR, f"{date_str}.log")
    record = {"ts": timestamp, "event": event_type, **payload}
    line = json.dumps(record, ensure_ascii=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    LOG_STREAM_HUB.publish(line)