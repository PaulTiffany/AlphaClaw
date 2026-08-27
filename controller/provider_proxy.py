"""Host-side metered OpenAI-compatible proxy for stock OmegaClaw benchmarks."""

from __future__ import annotations

import json
import secrets
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from threadkeeper_meter import ThreadKeeperRecorder


@dataclass(frozen=True)
class UpstreamSpec:
    display_name: str
    api_key_env: str
    base_url: str | None
    default_model: str


UPSTREAMS = {
    "asione": UpstreamSpec("ASIOne", "ASIONE_API_KEY", "https://api.asi1.ai/v1", "asi1-ultra"),
    "asicloud": UpstreamSpec(
        "ASICloud",
        "ASI_API_KEY",
        "https://inference.asicloud.cudos.org/v1",
        "minimax/minimax-m3",
    ),
    "openrouter": UpstreamSpec(
        "OpenRouter",
        "OPENROUTER_API_KEY",
        "https://openrouter.ai/api/v1",
        "z-ai/glm-5.2",
    ),
    "openai": UpstreamSpec("OpenAI", "OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-5.5"),
    "openaiapi": UpstreamSpec("OpenAIAPI", "OPENAIAPI_API_KEY", None, "qwen3.5:9b"),
}


class ProviderProxyError(RuntimeError):
    pass


Transport = Callable[[UpstreamSpec, str, str, dict[str, Any]], dict[str, Any]]


def _noop_completion(model: str) -> dict[str, Any]:
    return {
        "id": "alphaclaw-budget-stop",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "()"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _network_transport(
    spec: UpstreamSpec,
    api_key: str,
    base_url: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    forwarded = dict(body)
    if spec.display_name == "OpenRouter":
        usage = forwarded.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        forwarded["usage"] = {**usage, "include": True}

    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(forwarded).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise ProviderProxyError(
            f"{spec.display_name} returned HTTP {exc.code}: {detail}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderProxyError(f"{spec.display_name} request failed: {exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderProxyError(f"{spec.display_name} returned non-JSON response") from exc
    if not isinstance(payload, dict):
        raise ProviderProxyError(f"{spec.display_name} returned non-object JSON")
    return payload


class MeteredProviderGateway:
    """Forward stock Omega OpenAIAPI calls while metering and bounding the episode."""

    def __init__(
        self,
        *,
        upstream: UpstreamSpec,
        api_key: str,
        base_url: str,
        model: str,
        max_episode_calls: int,
        recorder: ThreadKeeperRecorder,
        transport: Transport = _network_transport,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        if not base_url:
            raise ValueError("base_url must not be empty")
        if not model:
            raise ValueError("model must not be empty")
        if max_episode_calls <= 0:
            raise ValueError("max_episode_calls must be positive")

        self.upstream = upstream
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_episode_calls = max_episode_calls
        self.recorder = recorder
        self.transport = transport
        self.proxy_token = secrets.token_urlsafe(24)

        self._lock = threading.Lock()
        self._phase = "boot"
        self._boot_attempts = 0
        self._episode_attempts = 0
        self._boot_completed = threading.Event()
        self._budget_exhausted = threading.Event()
        self._fatal_message = ""
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def fatal_message(self) -> str:
        with self._lock:
            return self._fatal_message

    @property
    def budget_exhausted(self) -> bool:
        return self._budget_exhausted.is_set()

    def mark_episode_started(self) -> None:
        with self._lock:
            self._phase = "episode"

    def wait_for_boot_call(self, timeout: float) -> bool:
        return self._boot_completed.wait(timeout)

    def _reserve_call(self) -> tuple[str, bool]:
        with self._lock:
            phase = self._phase
            if phase == "episode":
                if self._episode_attempts >= self.max_episode_calls:
                    self._budget_exhausted.set()
                    return phase, False
                self._episode_attempts += 1
            else:
                self._boot_attempts += 1
            return phase, True

    def _fail(self, message: str) -> None:
        with self._lock:
            self._fatal_message = message

    def handle_completion(self, body: dict[str, Any]) -> dict[str, Any]:
        requested_model = body.get("model")
        if requested_model != self.model:
            raise ProviderProxyError(
                f"Omega requested unexpected model {requested_model!r}; expected {self.model!r}"
            )

        phase, allowed = self._reserve_call()
        if not allowed:
            return _noop_completion(self.model)

        try:
            payload = self.transport(self.upstream, self.api_key, self.base_url, body)
            self.recorder.record(
                provider=self.upstream.display_name,
                model=self.model,
                phase=phase,
                response_payload=payload,
            )
        except Exception as exc:
            self._fail(str(exc))
            raise

        if phase == "boot":
            self._boot_completed.set()
        return payload

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "phase": self._phase,
                "boot_attempts": self._boot_attempts,
                "episode_attempts": self._episode_attempts,
                "max_episode_calls": self.max_episode_calls,
                "budget_exhausted": self._budget_exhausted.is_set(),
                "fatal_error": self._fatal_message or None,
            }

    def start(self) -> str:
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path.rstrip("/") != "/v1/chat/completions":
                    self.send_error(404)
                    return
                if self.headers.get("Authorization") != f"Bearer {gateway.proxy_token}":
                    self.send_error(401)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self.send_error(400)
                    return
                if length <= 0 or length > 16 * 1024 * 1024:
                    self.send_error(400)
                    return

                try:
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict):
                        raise ValueError("request JSON must be an object")
                    payload = gateway.handle_completion(body)
                    rendered = json.dumps(payload).encode("utf-8")
                except Exception as exc:
                    gateway._fail(str(exc))
                    rendered = json.dumps(
                        {"error": {"message": str(exc), "type": "alphaclaw_proxy_error"}}
                    ).encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(rendered)))
                    self.end_headers()
                    self.wfile.write(rendered)
                    return

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(rendered)))
                self.end_headers()
                self.wfile.write(rendered)

            def log_message(self, format: str, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="alphaclaw-provider-gateway",
        )
        self._thread.start()
        port = int(self._server.server_address[1])
        return f"http://host.docker.internal:{port}/v1/"

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None
