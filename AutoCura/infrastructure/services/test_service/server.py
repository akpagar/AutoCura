"""
AutoCura - Controlled Test Service

A deliberately trivial HTTP service (stdlib only, no dependencies) used
as a safe target for the recovery module's restart/scale/migration
actions. It is NOT part of AutoCura's own API -- it exists only to give
the recovery engine something real to restart inside a container,
without ever touching the host machine.
"""

import http.server
import json
import os
import signal
import socketserver
import threading
import time

PORT = int(os.environ.get("PORT", "9000"))
SERVICE_NAME = os.environ.get("SERVICE_NAME", "autocura-test-service")
START_TIME = time.time()


class Handler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            self._send_json({
                "service": SERVICE_NAME,
                "status": "healthy",
                "uptime_seconds": round(time.time() - START_TIME, 1),
            })
        else:
            self._send_json({"error": "not found"}, status=404)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # Quieter container logs -- one line per request is enough for a demo.
        print(f"[{SERVICE_NAME}] {self.address_string()} - {format % args}")


def main() -> None:
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"[{SERVICE_NAME}] listening on :{PORT}")
        # A process running as PID 1 in a container ignores SIGTERM unless it
        # installs a handler, which made every `docker stop/restart` wait the
        # full timeout before being killed. Shut down immediately instead.
        def _stop(*_args) -> None:
            threading.Thread(target=httpd.shutdown, daemon=True).start()

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
