# 20 — OpenAI-compatible LLM backend (Ollama, LM Studio, OpenRouter, OpenAI, Groq, Gemini…)

**Status:** PLANNED (spec only, not implemented). **Scheduled last** by the author: the project runs on Claude (`claude_cli` or `anthropic_api`) until the rest of the roadmap is done; this opens it to other and local models afterwards.

## 1. Problem

The two backends need a Claude subscription (`claude_cli`) or an Anthropic API key (`anthropic_api`). An open-source user may have neither, may prefer a **local model** (privacy, zero cost) or another provider. Most of the ecosystem exposes the same **OpenAI-style `/chat/completions` API**: Ollama, LM Studio, llama.cpp server, vLLM, OpenRouter, OpenAI, Groq, Together and Google's OpenAI-compatible Gemini endpoint. One generic backend covers them all.

## 2. Design

A third value `llm.backend: openai_compatible`, implemented as `OpenAiCompatibleBackend` behind the existing `Backend` protocol (`complete(system, prompt, schema, model) -> LlmResponse`). Budgets, retries, schema validation, the call log and the per-run call cap stay in `LlmClient`, untouched.

```yaml
llm:
  backend: openai_compatible
  base_url: http://localhost:11434/v1     # required; no trailing slash needed
  api_key_env: OPENAI_API_KEY             # NAME of the env var holding the key; optional for local servers
  structured_output: json_schema          # json_schema | json_object | prompt
  extra_headers: {}                       # e.g. OpenRouter's HTTP-Referer / X-Title (no secrets)
scoring:
  model: qwen2.5:14b-instruct             # free text: whatever the server calls the model
tailoring:
  model: qwen2.5:14b-instruct
```

- **Transport:** `httpx` (already a dependency), no new package. `POST {base_url}/chat/completions` with `model`, `messages` (system + user), `temperature: 0`, and the structured-output mode below. Timeout and attempts come from the existing `llm.timeout_seconds` / `llm.max_attempts`.
- **Structured output**, because servers differ:
  - `json_schema`: `response_format: {type: "json_schema", json_schema: {name, schema, strict: true}}` (OpenAI, OpenRouter, recent Ollama/LM Studio/vLLM).
  - `json_object`: `response_format: {type: "json_object"}` plus the schema printed in the system prompt (older servers, Groq).
  - `prompt`: no `response_format`; the schema and an instruction to answer with JSON only; the reply is parsed leniently (strip code fences, first JSON object). Always validated afterwards by the existing schema check; a failed validation is a normal retry (`LlmError`).
  - `jobhunter doctor --llm` probes the configured mode with a tiny schema and **suggests the next mode** if it fails.
- **Models:** no alias mapping. `scoring.model` and `tailoring.model` are passed verbatim; the default aliases (`haiku`, `sonnet`) are rejected for this backend with a clear config error ("set scoring.model and tailoring.model to the model names of your server").
- **Keys:** only through `api_key_env` (the **name** of an environment variable); the key is sent as `Authorization: Bearer …`, never written to config, logs, the call log, `fetch_log`-style tables or the UI, and redacted from error messages (same helper as spec 14 §3). A local server may need no key.
- **Usage and cost:** tokens from `usage.prompt_tokens` / `completion_tokens`; cost uses the existing `llm.api_prices` when the model is listed, else 0. **Budget rule:** with prices configured the daily USD budget applies (as `anthropic_api`); otherwise the per-run call cap applies (as `claude_cli`). The Settings AI card shows which rule is active.
- **Errors:** 401/403 → `LlmAuthError`; 429 → `LlmLimitReached` honouring `Retry-After`; 5xx, timeouts and connection errors → retried; "connection refused" on a localhost URL → message "is Ollama / LM Studio running?"; a 404 on `/chat/completions` → "check base_url (it usually ends with /v1)".
- **Privacy note in the UI and README:** with a remote provider the CV items and posting text go to that provider; with a local server nothing leaves the machine. The contact header is never sent in any case (06).

## 3. Quality guardrails for small models

Local models are weaker and the pipeline must not silently degrade:

- The CV-verification step (invented numbers, names, dates, unknown item ids) already runs in code and is **backend-independent**: a bad generation is rejected, not shipped. Documented as the reason local models are safe to try.
- `jobhunter calibrate` (05) is the recommended first command after switching: it scores a few known postings and shows the spread; the docs say what a healthy spread looks like and when to raise `score_threshold`.
- Scoring batch size can be lowered for small context windows (`scoring.batch_size`); `doctor --llm` prints the model's reported context length when the server exposes it and warns if `max_description_tokens × batch_size` would not fit.
- Tailoring in `select` mode needs only ids and short text, so it works with modest models; the translation step is the most demanding and is flagged in the docs.

## 4. UI and CLI changes

- Settings → AI & documents: backend selector gains *Any OpenAI-compatible server*; fields for `base_url`, `api_key_env` (name only, with a "set / not set" indicator that reads the environment of the running UI process, never the value), `structured_output`, and the two model names. The locked-fields rule is unchanged: nothing here chooses a file or runs a program.
- `jobhunter doctor` shows the backend, URL, key "set / not set", whether `/models` is reachable and the model is listed, and the structured-output probe.
- Presets documented in `docs/RUNNING_CHEAP.md` (spec 19 §6) with copy-paste configs: Ollama, LM Studio, OpenRouter, OpenAI, Groq, Gemini's OpenAI-compatible endpoint, and a note on rough cost per 100 scored postings per option.

## 5. Tests

- Request shape per `structured_output` mode (respx): URL, headers, body, no key in the body.
- Parsing: clean JSON, fenced JSON, JSON with leading prose (lenient mode), invalid JSON → `LlmError`, schema mismatch → retry through `LlmClient`.
- Errors: 401, 429 with `Retry-After`, 5xx then success, timeout, connection refused, 404.
- Key handling: read from the named env var, absent key allowed for localhost, key never in logs, the call log or error text.
- Budget rule selection (prices present vs absent); config validation rejects the default aliases for this backend.
- No test touches the network or a real model.

## 6. Tasks

- [ ] `OpenAiCompatibleBackend`, config fields and validation, `build_backend` wiring.
- [ ] Structured-output modes, lenient JSON extraction, usage/cost, error mapping.
- [ ] Shared credential redaction helper (also used by 14).
- [ ] `doctor --llm` probe and suggestions; context-length warning.
- [ ] Settings UI fields and the active-budget-rule note; README (privacy table per backend, cost note) and `docs/RUNNING_CHEAP.md` presets.
- [ ] Real runs against Ollama and one hosted provider; record the findings (models that score and tailor acceptably) in this spec.
- [ ] This spec marked done.

## 7. Acceptance criteria

- [ ] With only a local Ollama model configured, `search → score → tailor` completes and the verification still rejects invented facts.
- [ ] Switching backends needs only `config.yaml` (or Settings) changes; no code or environment hacks.
- [ ] No API key can appear in any file, log or page; a test enforces it.
- [ ] A misconfigured URL, model or key produces a message that says what to fix.
