"""Host-side metered OpenAI-compatible proxy for stock OmegaClaw benchmarks."""

from __future__ import annotations

import json
import secrets
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

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


class BootBudgetExhausted(ProviderProxyError):
    """The controller refused upstream authorization for a boot-phase request.

    Raised instead of forwarding, so no second upstream POST is ever issued. This is
    a controller authorization decision, not an upstream failure, so it must not be
    recorded as the gateway's fatal error when a successful boot call already exists.
    """


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


def _append_raw_usage_receipt(
    recorder: ThreadKeeperRecorder,
    *,
    provider: str,
    model: str,
    phase: str,
    payload: dict[str, Any],
) -> None:
    """Persist provider-returned usage before invoking any third-party witness."""
    path = Path(recorder.raw_usage_log)
    record = {
        "ts": time.time(),
        "thread_id": recorder.run_id,
        "node_role": f"omega_{phase}",
        "phase": phase,
        "provider": provider,
        "model": model,
        "usage": payload.get("usage"),
    }
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    except OSError as exc:
        raise RuntimeError("could not persist raw provider usage receipt") from exc


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
        max_boot_calls: int,
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
        if max_boot_calls <= 0:
            raise ValueError("max_boot_calls must be positive")

        self.upstream = upstream
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_episode_calls = max_episode_calls
        self.max_boot_calls = max_boot_calls
        self.recorder = recorder
        self.transport = transport
        self.proxy_token = secrets.token_urlsafe(24)

        self._lock = threading.Lock()
        self._phase = "boot"
        self._boot_attempts = 0
        self._episode_attempts = 0
        self._boot_completed = threading.Event()
        self._episode_release = threading.Event()
        self._closed = threading.Event()
        self._budget_exhausted = threading.Event()
        self._boot_budget_exhausted = threading.Event()
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

    @property
    def boot_budget_exhausted(self) -> bool:
        return self._boot_budget_exhausted.is_set()

    def mark_episode_started(self) -> None:
        """Classify subsequent Omega provider requests as post-handoff episode calls."""
        with self._lock:
            self._phase = "episode"

    def release_episode_calls(self) -> None:
        """Allow a queued episode provider request to reach the real upstream."""
        self._episode_release.set()

    def wait_for_boot_call(self, timeout: float) -> bool:
        """Wait for the first successful boot call, or for the boot budget to bind.

        Returns False promptly once the controller has refused boot-phase
        authorization, so a run whose boot budget is exhausted without a successful
        upstream call terminates immediately instead of stalling for the full wait.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._boot_completed.is_set():
                return True
            if self._boot_budget_exhausted.is_set():
                return False
            time.sleep(0.05)
        return self._boot_completed.is_set()

    def _reserve_call(self) -> tuple[str, bool]:
        with self._lock:
            phase = self._phase
            if phase == "episode":
                if self._episode_attempts >= self.max_episode_calls:
                    self._budget_exhausted.set()
                    return phase, False
                self._episode_attempts += 1
            else:
                if self._boot_attempts >= self.max_boot_calls:
                    self._boot_budget_exhausted.set()
                    # Only claim the fatal slot when no successful boot call exists.
                    # A refusal after a healthy boot must not abort the episode.
                    # NOTE: self._lock is held here and is not reentrant, so assign
                    # directly rather than calling _fail().
                    if not self._boot_completed.is_set() and not self._fatal_message:
                        self._fatal_message = (
                            "stock boot provider budget exhausted before a successful "
                            "boot call; controller refused upstream authorization"
                        )
                    return phase, False
                self._boot_attempts += 1
            return phase, True

    def _fail(self, message: str) -> None:
        with self._lock:
            self._fatal_message = message

    def _wait_until_episode_released(self) -> None:
        if not self._episode_release.wait(timeout=60):
            raise ProviderProxyError("episode provider request was never released by controller")
        if self._closed.is_set():
            raise ProviderProxyError("provider gateway closed before episode request was released")

    def handle_completion(self, body: dict[str, Any]) -> dict[str, Any]:
        requested_model = body.get("model")
        if requested_model != self.model:
            raise ProviderProxyError(
                f"Omega requested unexpected model {requested_model!r}; expected {self.model!r}"
            )

        phase, allowed = self._reserve_call()
        if not allowed:
            if phase == "boot":
                # Refuse rather than fabricate: a synthetic completion would enter
                # Omega's context as genuine model output and contaminate the boot
                # behavior being observed. An error is a condition Omega can meet
                # in the wild; an invented assistant turn is not.
                raise BootBudgetExhausted(
                    "stock boot provider budget exhausted after "
                    f"{self.max_boot_calls} upstream attempt(s); "
                    "controller refused further boot-phase provider authorization"
                )
            return _noop_completion(self.model)
        if phase == "episode":
            self._wait_until_episode_released()

        try:
            payload = self.transport(self.upstream, self.api_key, self.base_url, body)
            _append_raw_usage_receipt(
                self.recorder,
                provider=self.upstream.display_name,
                model=self.model,
                phase=phase,
                payload=payload,
            )
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
                "max_boot_calls": self.max_boot_calls,
                "episode_released": self._episode_release.is_set(),
                "budget_exhausted": self._budget_exhausted.is_set(),
                "boot_budget_exhausted": self._boot_budget_exhausted.is_set(),
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
                        raise TypeError("request JSON must be an object")
                    payload = gateway.handle_completion(body)
                    rendered = json.dumps(payload).encode("utf-8")
                except BootBudgetExhausted as exc:
                    # Deliberately does not call gateway._fail(): refusing to fund a
                    # boot retry is a controller decision, and must not overwrite the
                    # gateway's fatal state when a boot call already succeeded.
                    rendered = json.dumps(
                        {
                            "error": {
                                "message": str(exc),
                                "type": "alphaclaw_boot_budget_exhausted",
                            }
                        }
                    ).encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(rendered)))
                    self.end_headers()
                    self.wfile.write(rendered)
                    return
                except (
                    json.JSONDecodeError,
                    ProviderProxyError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                ) as exc:
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
        self._closed.set()
        self._episode_release.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None
