"""HTTP server.

Exposes the agent over a small JSON-over-HTTP API:

  POST /intent           Run one user request through the captain.
  GET  /skills           Return the workspace skill overview string.
  GET  /agents           Return the agent roster.
  GET  /logs/stream      Server-Sent Events feed of agent.log lines.
  GET  /traces/...       Trace inspection (delegated to trace_api).
  GET  /metrics/...      Aggregated metrics (delegated to trace_api).

The handler class is produced by ``make_handler_class``: a factory that
captures the AgentManager, AgentTurnRunner, and LogStreamHub in a closure
so handler instances created by ``ThreadingHTTPServer`` can reach them
without relying on class-level globals. This replaces the original
``AgentHTTPRequestHandler.manager = manager`` pattern from app.py.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty
from typing import Any, Dict, Type, TYPE_CHECKING

from tracing import start_trace
from trace_api import handle_trace_request

from core.agent import list_agents
from core.fs import list_folder_overview
from core.tools import supervision

if TYPE_CHECKING:
    from core.agent import AgentManager
    from core.logging_hub import LogStreamHub
    from core.runner import AgentTurnRunner


# ---------------------------------------------------------------------------
# Handler factory
# ---------------------------------------------------------------------------

def make_handler_class(
    manager: "AgentManager",
    runner: "AgentTurnRunner",
    hub: "LogStreamHub",
) -> Type[BaseHTTPRequestHandler]:
    """Build a handler class with its dependencies captured by closure.

    ``ThreadingHTTPServer`` instantiates a fresh handler per request, so
    we cannot pass instance state — but we can hand it a class whose
    methods reach the manager/runner/hub through enclosing scope.
    """

    class AgentHTTPRequestHandler(BaseHTTPRequestHandler):
        """HTTP handler for the agent.

        All persistent state (manager, runner, hub) is captured by the
        enclosing closure; this class itself is pure logic.
        """

        # --- response helpers --------------------------------------

        def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # --- HTTP verbs --------------------------------------------

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_POST(self) -> None:
            if self.path != "/intent":
                self._send_json(404, {"error": "Not found."})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                data = json.loads(raw.decode("utf-8")) if raw else {}
            except json.JSONDecodeError:
                self._send_json(400, {"error": "Invalid JSON body."})
                return
            user_input = data.get("input")
            if not isinstance(user_input, str) or not user_input.strip():
                self._send_json(400, {"error": "Missing 'input' string."})
                return

            with start_trace(
                "agent.request",
                {"intent.text": user_input.strip()[:200]},
            ) as handle:
                response_text = runner.process_user_input(
                    manager, user_input.strip()
                )
                handle.set("response.length", len(response_text))
                revisions = supervision.pop_revisions(handle.trace_id)

            self._send_json(
                200,
                {
                    "response": response_text,
                    "trace_id": handle.trace_id,
                    "skill_revisions": revisions,
                },
            )

        def do_GET(self) -> None:
            if self.path == "/skills":
                self._send_json(200, {"skills": list_folder_overview(".")})
                return
            if self.path == "/agents":
                self._send_json(200, list_agents(manager.agents))
                return
            if self.path == "/logs/stream":
                self._handle_log_stream()
                return

            # /traces, /traces/{id}, /metrics/summary, /metrics/timeseries
            if handle_trace_request(
                self.path,
                lambda code, body: self._send_json(code, body),
            ):
                return

            self._send_json(404, {"error": "Not found."})

        # --- SSE ---------------------------------------------------

        def _handle_log_stream(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            queue = hub.subscribe()
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
                while True:
                    try:
                        message = queue.get(timeout=15)
                        safe_message = message.replace("\n", "\\n")
                        payload = f"data: {safe_message}\n\n".encode("utf-8")
                        self.wfile.write(payload)
                        self.wfile.flush()
                    except Empty:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                hub.unsubscribe(queue)

        # --- silence default access logging ------------------------

        def log_message(self, format: str, *args: Any) -> None:
            return

    return AgentHTTPRequestHandler


# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------

def serve(
    host: str,
    port: int,
    manager: "AgentManager",
    runner: "AgentTurnRunner",
    hub: "LogStreamHub",
) -> None:
    """Run the threaded HTTP server until interrupted.

    Catches ``KeyboardInterrupt`` for a clean shutdown message in the CLI
    case where the operator hits Ctrl-C in the container's foreground.
    """
    handler_cls = make_handler_class(manager, runner, hub)
    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"Agent HTTP server on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")