from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OMEGA_SHA = "3d711e4b9f5254ae94f31123ca242f60cfd97d29"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in {"/", "/health"}:
            self.send_error(404)
            return
        payload = json.dumps(
            {
                "status": "ok",
                "resident": "alphaclaw-omega",
                "provider": "ASIOne",
                "model": "asi1-mini",
                "omega_source_sha": OMEGA_SHA,
                "alpha_source_sha": os.environ.get("ALPHACLAW_SOURCE_SHA", ""),
            },
            sort_keys=True,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 7860), Handler).serve_forever()
