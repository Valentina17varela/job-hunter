"""LLM access behind one interface (see specs/05-scoring.md §1).

Two backends: ``claude_cli`` (the person's Claude subscription through ``claude -p``, no API
key) and ``anthropic_api`` (SDK + API key). Callers only see ``LlmClient.call``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from jobhunter.config import Config, LlmConfig

T = TypeVar("T", bound=BaseModel)


class LlmError(Exception):
    """A call failed in a way retrying will not fix (or retries ran out)."""


class LlmAuthError(LlmError):
    """The backend is not authenticated."""


class LlmLimitReached(LlmError):
    """A budget or the provider's usage limit stops further calls for now."""


@dataclass
class LlmResponse:
    data: dict[str, Any]
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache_read: int = 0
    cost_usd: float = 0.0


class Backend(Protocol):
    def complete(
        self, *, system: str, prompt: str, schema: dict[str, Any], model: str
    ) -> LlmResponse:
        """Run one call and return the parsed JSON object. Raise LlmError subclasses."""
        ...


# --- claude -p (subscription) ----------------------------------------------------------------


def clean_env(env: Mapping[str, str]) -> dict[str, str]:
    """Environment for the `claude` subprocess without inherited Claude/Anthropic credentials.

    Dropping them makes the CLI use the person's own login even when launched from inside
    another Claude session, and stops ANTHROPIC_API_KEY from silently switching to API billing.
    """
    keep_exceptions = {"CLAUDE_CONFIG_DIR"}
    return {
        k: v
        for k, v in env.items()
        if k in keep_exceptions or not (k.startswith("ANTHROPIC_") or k.startswith("CLAUDE"))
    }


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)
_LIMIT_RE = re.compile(
    r"usage limit|limit reached|rate limit|quota|overloaded|too many requests", re.I
)
_AUTH_RE = re.compile(
    r"401|authenticate|not logged in|invalid bearer|please run .*login|/login", re.I
)


def _parse_json_text(text: str) -> dict[str, Any]:
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    try:
        data = json.loads(cleaned)
    except ValueError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


class ClaudeCliBackend:
    """Calls ``claude -p`` in an empty temp directory with no tools, hooks or settings."""

    def __init__(self, cfg: LlmConfig, environ: Mapping[str, str] | None = None) -> None:
        self.cfg = cfg
        self._environ = environ if environ is not None else os.environ

    def _env(self) -> dict[str, str]:
        env = clean_env(self._environ)
        if self.cfg.max_thinking_tokens is not None:
            env["MAX_THINKING_TOKENS"] = str(self.cfg.max_thinking_tokens)
        return env

    def command(self, system: str, schema: dict[str, Any], model: str) -> list[str]:
        cmd = [
            self.cfg.claude_path, "-p", "--model", model, "--tools", "",
            "--system-prompt", system, "--setting-sources", "",
            "--disable-slash-commands", "--no-session-persistence",
            "--output-format", "json", "--json-schema", json.dumps(schema),
        ]  # fmt: skip
        if self.cfg.effort:
            cmd += ["--effort", self.cfg.effort]
        return cmd

    def complete(
        self, *, system: str, prompt: str, schema: dict[str, Any], model: str
    ) -> LlmResponse:
        if shutil.which(self.cfg.claude_path) is None:
            raise LlmError(
                f"'{self.cfg.claude_path}' not found. Install Claude Code, or set "
                "llm.claude_path / llm.backend in config.yaml."
            )
        with tempfile.TemporaryDirectory() as tmp:
            try:
                proc = subprocess.run(
                    self.command(system, schema, model),
                    input=prompt, capture_output=True, text=True, cwd=tmp,
                    env=self._env(), timeout=self.cfg.timeout_seconds, check=False,
                )  # fmt: skip
            except subprocess.TimeoutExpired as exc:
                raise LlmError(f"claude timed out after {self.cfg.timeout_seconds}s") from exc
        return self._parse(proc, model)

    def _parse(self, proc: subprocess.CompletedProcess[str], model: str) -> LlmResponse:
        raw = (proc.stdout or "").strip()
        try:
            envelope = json.loads(raw)
        except ValueError as exc:
            message = (proc.stderr or raw)[:300]
            self._raise_for_text(message)
            raise LlmError(
                f"claude exited {proc.returncode} with unreadable output: {message}"
            ) from exc
        if not isinstance(envelope, dict):
            raise LlmError("unexpected claude output")
        if envelope.get("is_error") or proc.returncode != 0:
            message = str(envelope.get("result") or proc.stderr or "claude reported an error")
            self._raise_for_text(message)
            raise LlmError(message[:300])
        structured = envelope.get("structured_output")
        try:
            data = (
                structured
                if isinstance(structured, dict)
                else _parse_json_text(str(envelope.get("result") or ""))
            )
        except ValueError as exc:
            raise LlmError(f"response is not valid JSON: {exc}") from exc
        usage = envelope.get("usage") or {}
        return LlmResponse(
            data=data,
            model=model,
            tokens_in=int(usage.get("input_tokens") or 0)
            + int(usage.get("cache_creation_input_tokens") or 0),
            tokens_out=int(usage.get("output_tokens") or 0),
            tokens_cache_read=int(usage.get("cache_read_input_tokens") or 0),
            cost_usd=float(envelope.get("total_cost_usd") or 0.0),
        )

    @staticmethod
    def _raise_for_text(message: str) -> None:
        if _AUTH_RE.search(message):
            raise LlmAuthError(
                "claude is not logged in. Run `claude auth login` in your own terminal "
                f"(details: {message[:120]})"
            )
        if _LIMIT_RE.search(message):
            raise LlmLimitReached(f"claude usage limit reached: {message[:160]}")


def claude_login_status(
    cfg: LlmConfig, environ: Mapping[str, str] | None = None
) -> tuple[bool, str]:
    """Whether the `claude` CLI is logged in (for `jobhunter doctor`)."""
    if shutil.which(cfg.claude_path) is None:
        return False, f"'{cfg.claude_path}' not found"
    try:
        proc = subprocess.run(
            [cfg.claude_path, "auth", "status"], capture_output=True, text=True, timeout=30,
            env=clean_env(environ if environ is not None else os.environ), check=False,
        )  # fmt: skip
        status = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, ValueError, OSError) as exc:
        return False, f"could not read `claude auth status`: {exc}"
    if status.get("loggedIn"):
        return True, f"logged in ({status.get('authMethod', 'unknown')})"
    return False, "not logged in — run `claude auth login` in your terminal"


# --- Anthropic API ---------------------------------------------------------------------------


class AnthropicApiBackend:
    """Uses the Anthropic SDK with forced tool output and prompt caching on the system prompt."""

    def __init__(self, cfg: LlmConfig, client: Any | None = None, max_tokens: int = 4096) -> None:
        self.cfg = cfg
        self.max_tokens = max_tokens
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise LlmAuthError("ANTHROPIC_API_KEY is not set")
            import anthropic

            self._client = anthropic.Anthropic(timeout=self.cfg.timeout_seconds)
        return self._client

    def complete(
        self, *, system: str, prompt: str, schema: dict[str, Any], model: str
    ) -> LlmResponse:
        client = self._get_client()
        try:
            message = client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}],
                tools=[
                    {"name": "respond", "description": "Return the result.", "input_schema": schema}
                ],
                tool_choice={"type": "tool", "name": "respond"},
            )
        except Exception as exc:  # noqa: BLE001 - map SDK errors to ours
            text = f"{type(exc).__name__}: {exc}"
            if _AUTH_RE.search(text):
                raise LlmAuthError(text) from exc
            if _LIMIT_RE.search(text):
                raise LlmLimitReached(text) from exc
            raise LlmError(text) from exc
        block = next((b for b in message.content if getattr(b, "type", "") == "tool_use"), None)
        if block is None or not isinstance(block.input, dict):
            raise LlmError("response contained no structured output")
        usage = message.usage
        tin = int(getattr(usage, "input_tokens", 0) or 0)
        tout = int(getattr(usage, "output_tokens", 0) or 0)
        cache = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        price = self.cfg.api_prices.get(model)
        cost = (tin * price[0] + tout * price[1]) / 1_000_000 if price else 0.0
        return LlmResponse(block.input, model, tin, tout, cache, cost)


def build_backend(cfg: Config) -> Backend:
    if cfg.llm.backend == "anthropic_api":
        return AnthropicApiBackend(cfg.llm)
    return ClaudeCliBackend(cfg.llm)


# --- client: budget, retries, validation, call log ---------------------------------------------


class LlmClient:
    """The single place that calls the LLM: enforces the budget, retries and logs every call."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        backend: Backend,
        *,
        max_calls: int,
        daily_budget_usd: float | None = None,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.conn = conn
        self.backend = backend
        self.max_calls = max_calls
        self.daily_budget_usd = daily_budget_usd
        self.max_attempts = max_attempts
        self._sleep = sleep
        self.calls = 0

    def spent_today(self) -> float:
        today = datetime.now(UTC).date().isoformat()
        row = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM llm_calls WHERE created_at >= ?", (today,)
        ).fetchone()
        return float(row[0])

    def _check_budget(self) -> None:
        if self.calls >= self.max_calls:
            raise LlmLimitReached(f"reached the cap of {self.max_calls} LLM calls for this run")
        if self.daily_budget_usd is not None and self.spent_today() >= self.daily_budget_usd:
            raise LlmLimitReached(f"daily budget of ${self.daily_budget_usd:.2f} reached")

    def call(
        self,
        *,
        stage: str,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        model: str,
        parse: type[T],
        job_id: int | None = None,
    ) -> T:
        """One logical call: transient errors and invalid output are retried with backoff."""
        feedback = ""
        last_error = "unknown error"
        for attempt in range(self.max_attempts):
            self._check_budget()
            self.calls += 1
            try:
                response = self.backend.complete(
                    system=system, prompt=prompt + feedback, schema=schema, model=model
                )
            except (LlmAuthError, LlmLimitReached):
                raise
            except LlmError as exc:
                last_error = str(exc)
                self._sleep(2**attempt)
                continue
            self._record(stage, job_id, response)
            try:
                return parse.model_validate(response.data)
            except ValidationError as exc:
                last_error = f"invalid response: {exc.errors()[0]['msg']}"
                feedback = (
                    "\n\nYour previous answer was rejected: "
                    f"{exc.errors()[0]['loc']} {exc.errors()[0]['msg']}. Return valid JSON only."
                )
        raise LlmError(f"gave up after {self.max_attempts} attempts: {last_error}")

    def _record(self, stage: str, job_id: int | None, r: LlmResponse) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO llm_calls(stage, model, job_id, tokens_in, tokens_out, "
                "tokens_cache_read, cost_usd, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (stage, r.model, job_id, r.tokens_in, r.tokens_out, r.tokens_cache_read,
                 r.cost_usd, datetime.now(UTC).isoformat()),
            )  # fmt: skip
