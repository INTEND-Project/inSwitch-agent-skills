#!/usr/bin/env python3
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse


DATA_PATH = Path(__file__).with_name("services.json")
SERVICES_PAYLOAD = json.loads(DATA_PATH.read_text(encoding="utf-8"))


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/info/services":
            self._send_json(SERVICES_PAYLOAD)
            return
        if path == "/status":
            self._send_json({})
            return
        self._send_json({"error": "not found"}, status=404)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8001), Handler)
    server.serve_forever()
