from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

OMEGA_SHA = "3d711e4b9f5254ae94f31123ca242f60cfd97d29"


def route_path(target: str) -> str:
    return urlsplit(target).path


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if route_path(self.path) not in {"/", "/health"}:
            self.send_error(404)
            return
        payload = json.dumps(
            {
                "status": "ok",
                "resident": "minimum-authority-omega",
                "provider": "ASIOne",
                "model": "asi1-mini",
                "boot_inference_cycles": int(
                    os.environ.get("ALPHACLAW_BOOT_LOOPS", "0")
                ),
                "cycles_per_new_human_input": int(
                    os.environ.get("ALPHACLAW_MAX_NEW_INPUT_LOOPS", "8")
                ),
                "scheduled_wake_cycles": int(
                    os.environ.get("ALPHACLAW_MAX_WAKE_LOOPS", "0")
                ),
                "history_recall_chars": int(
                    os.environ.get("ALPHACLAW_MAX_HISTORY_CHARS", "0")
                ),
                "persistent_history": bool(
                    int(os.environ.get("ALPHACLAW_PERSIST_HISTORY", "0"))
                ),
                "conversation_content_logging": bool(
                    int(os.environ.get("ALPHACLAW_LOG_CONVERSATION_CONTENT", "0"))
                ),
                "model_actions": [
                    item
                    for item in os.environ.get("ALPHACLAW_MODEL_ACTIONS", "send").split(",")
                    if item
                ],
                "resident_plugins": [
                    item
                    for item in os.environ.get(
                        "ALPHACLAW_RESIDENT_PLUGINS", "wschat,asione"
                    ).split(",")
                    if item
                ],
                "omega_source_sha": OMEGA_SHA,
                "wrapper_source_sha": os.environ.get("ALPHACLAW_SOURCE_SHA", ""),
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
