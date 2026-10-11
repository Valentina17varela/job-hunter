import json
import stat
import sys
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from jobhunter.config import LlmConfig
from jobhunter.db import connect
from jobhunter.llm import (
    AnthropicApiBackend,
    ClaudeCliBackend,
    LlmAuthError,
    LlmClient,
    LlmError,
    LlmLimitReached,
    LlmResponse,
    claude_login_status,
    clean_env,
)

SCHEMA = {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}


class Out(BaseModel):
    n: int


def fake_claude(tmp_path, stdout: str, code: int = 0):
    """An executable that records its args/stdin/env and prints a canned stdout."""
    log = tmp_path / "log.json"
    script = tmp_path / "claude"
    script.write_text(
        f"#!{sys.executable}\nimport json, os, sys\n"
        f"json.dump({{'argv': sys.argv[1:], 'stdin': sys.stdin.read(), 'env': dict(os.environ),"
        f" 'cwd': os.getcwd()}}, open({str(log)!r}, 'w'))\n"
        f"sys.stdout.write({stdout!r})\nsys.exit({code})\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script), log


def cli(path):
    return ClaudeCliBackend(LlmConfig(claude_path=path), environ={"PATH": "/usr/bin", "HOME": "/h"})


def test_clean_env_drops_claude_and_anthropic_credentials():
    env = {
        "PATH": "/bin", "HOME": "/h", "ANTHROPIC_API_KEY": "k", "ANTHROPIC_AUTH_TOKEN": "t",
        "ANTHROPIC_BASE_URL": "u", "CLAUDE_CODE_ENTRYPOINT": "x", "CLAUDECODE": "1",
        "CLAUDE_AGENT_SDK_VERSION": "1", "CLAUDE_CONFIG_DIR": "/keep",
    }  # fmt: skip
    assert clean_env(env) == {"PATH": "/bin", "HOME": "/h", "CLAUDE_CONFIG_DIR": "/keep"}


def test_cli_backend_command_prompt_env_and_structured_output(tmp_path):
    envelope = {"is_error": False, "structured_output": {"n": 7},
                "usage": {"input_tokens": 10, "output_tokens": 3, "cache_read_input_tokens": 5},
                "total_cost_usd": 0.01}  # fmt: skip
    path, log = fake_claude(tmp_path, json.dumps(envelope))
    result = cli(path).complete(system="SYS", prompt="PROMPT TEXT", schema=SCHEMA, model="haiku")
    assert result.data == {"n": 7}
    assert (result.tokens_in, result.tokens_out, result.tokens_cache_read) == (10, 3, 5)
    assert result.cost_usd == pytest.approx(0.01)
    seen = json.loads(log.read_text())
    argv = seen["argv"]
    assert seen["stdin"] == "PROMPT TEXT"
    assert argv[:1] == ["-p"] and "--no-session-persistence" in argv
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--system-prompt") + 1] == "SYS"
    assert json.loads(argv[argv.index("--json-schema") + 1]) == SCHEMA
    assert argv[argv.index("--effort") + 1] == "low"
    assert not any(k.startswith(("ANTHROPIC", "CLAUDE")) for k in seen["env"])
    assert seen["cwd"] != str(tmp_path) and "job-hunter" not in seen["cwd"]


def test_cli_backend_parses_json_in_result_text_with_fences(tmp_path):
    envelope = {"is_error": False, "result": '```json\n{"n": 3}\n```'}
    path, _ = fake_claude(tmp_path, json.dumps(envelope))
    assert cli(path).complete(system="s", prompt="p", schema=SCHEMA, model="haiku").data == {"n": 3}


def test_cli_backend_auth_limit_and_generic_errors(tmp_path):
    auth, _ = fake_claude(
        tmp_path, json.dumps({"is_error": True, "result": "401 Invalid bearer token"})
    )
    with pytest.raises(LlmAuthError, match="claude auth login"):
        cli(auth).complete(system="s", prompt="p", schema=SCHEMA, model="haiku")
    limit, _ = fake_claude(
        tmp_path, json.dumps({"is_error": True, "result": "Usage limit reached"})
    )
    with pytest.raises(LlmLimitReached):
        cli(limit).complete(system="s", prompt="p", schema=SCHEMA, model="haiku")
    other, _ = fake_claude(tmp_path, json.dumps({"is_error": True, "result": "boom"}), code=1)
    with pytest.raises(LlmError, match="boom"):
        cli(other).complete(system="s", prompt="p", schema=SCHEMA, model="haiku")
    garbage, _ = fake_claude(tmp_path, "not json at all")
    with pytest.raises(LlmError, match="unreadable"):
        cli(garbage).complete(system="s", prompt="p", schema=SCHEMA, model="haiku")


def test_cli_backend_missing_executable():
    backend = ClaudeCliBackend(LlmConfig(claude_path="definitely-not-installed"), environ={})
    with pytest.raises(LlmError, match="not found"):
        backend.complete(system="s", prompt="p", schema=SCHEMA, model="haiku")


def test_claude_login_status(tmp_path):
    ok, _ = fake_claude(tmp_path, json.dumps({"loggedIn": True, "authMethod": "oauth_token"}))
    assert claude_login_status(LlmConfig(claude_path=ok), environ={"PATH": "/usr/bin"})[0] is True
    no, _ = fake_claude(tmp_path, json.dumps({"loggedIn": False}))
    status = claude_login_status(LlmConfig(claude_path=no), environ={"PATH": "/usr/bin"})
    assert status[0] is False and "claude auth login" in status[1]
    assert claude_login_status(LlmConfig(claude_path="nope-not-here"))[0] is False


# --- API backend with a fake SDK client --------------------------------------------------------


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.kwargs = response, error, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


def api_response(data):
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", input=data)],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=200, cache_read_input_tokens=50),
    )


def test_api_backend_forces_tool_output_caches_system_and_prices_tokens():
    messages = FakeMessages(api_response({"n": 1}))
    cfg = LlmConfig(backend="anthropic_api", api_prices={"m": (1.0, 5.0)})
    backend = AnthropicApiBackend(cfg, client=SimpleNamespace(messages=messages))
    result = backend.complete(system="SYS", prompt="P", schema=SCHEMA, model="m")
    assert result.data == {"n": 1} and result.cost_usd == pytest.approx(0.002)
    kw = messages.kwargs
    assert kw["tool_choice"] == {"type": "tool", "name": "respond"}
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_api_backend_maps_errors(monkeypatch):
    cfg = LlmConfig(backend="anthropic_api")
    auth = AnthropicApiBackend(
        cfg, client=SimpleNamespace(messages=FakeMessages(error=RuntimeError("401 authenticate")))
    )
    with pytest.raises(LlmAuthError):
        auth.complete(system="s", prompt="p", schema=SCHEMA, model="m")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LlmAuthError, match="ANTHROPIC_API_KEY"):
        AnthropicApiBackend(cfg).complete(system="s", prompt="p", schema=SCHEMA, model="m")


# --- client: budget, retries, logging ------------------------------------------------------------


class Scripted:
    """Backend returning queued responses or raising queued errors."""

    def __init__(self, *items):
        self.items, self.prompts = list(items), []

    def complete(self, *, system, prompt, schema, model):
        self.prompts.append(prompt)
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return LlmResponse(data=item, model=model, tokens_in=100, tokens_out=10, cost_usd=0.5)


@pytest.fixture
def conn(tmp_path):
    return connect(tmp_path / "t.db")


def client(conn, backend, **kw):
    return LlmClient(conn, backend, max_calls=kw.pop("max_calls", 10), sleep=lambda s: None, **kw)


def call(c):
    return c.call(stage="score", system="s", prompt="p", schema=SCHEMA, model="haiku", parse=Out)


def test_client_returns_validated_model_and_logs_the_call(conn):
    c = client(conn, Scripted({"n": 4}))
    assert call(c) == Out(n=4)
    row = conn.execute(
        "SELECT stage, model, tokens_in, tokens_out, cost_usd FROM llm_calls"
    ).fetchone()
    assert tuple(row) == ("score", "haiku", 100, 10, 0.5)


def test_client_retries_transient_errors_then_succeeds(conn):
    backend = Scripted(LlmError("timeout"), LlmError("timeout"), {"n": 1})
    assert call(client(conn, backend)).n == 1
    assert len(backend.prompts) == 3


def test_client_retries_invalid_output_with_feedback(conn):
    backend = Scripted({"n": "not a number"}, {"n": 2})
    assert call(client(conn, backend)).n == 2
    assert "rejected" in backend.prompts[1] and "rejected" not in backend.prompts[0]


def test_client_gives_up_after_max_attempts(conn):
    backend = Scripted(LlmError("a"), LlmError("b"), LlmError("c"))
    with pytest.raises(LlmError, match="gave up after 3 attempts: c"):
        call(client(conn, backend))


def test_client_does_not_retry_auth_or_limit_errors(conn):
    backend = Scripted(LlmAuthError("login"))
    with pytest.raises(LlmAuthError):
        call(client(conn, backend))
    assert len(backend.prompts) == 1


def test_client_call_cap(conn):
    c = client(conn, Scripted({"n": 1}, {"n": 2}), max_calls=1)
    call(c)
    with pytest.raises(LlmLimitReached, match="cap of 1"):
        call(c)


def test_client_daily_usd_budget(conn):
    c = client(conn, Scripted({"n": 1}, {"n": 2}), daily_budget_usd=0.4)
    call(c)  # logs 0.5 USD
    with pytest.raises(LlmLimitReached, match="daily budget"):
        call(c)
