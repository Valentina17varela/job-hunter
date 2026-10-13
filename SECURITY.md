# Security policy

## Reporting a vulnerability

Please **do not open a public issue**. Report it privately through GitHub: *Security → Report a vulnerability* on this repository. Say what you found, how to reproduce it and what it could do. You will get an answer within a few days; fixes are released as soon as they are verified, and you are credited if you wish.

## What the project protects

Job Hunter is a **single-person, local tool**. Its security model:

- The web UI listens on `127.0.0.1` only, checks `Host` and `Origin` on every request, accepts writes only as JSON, escapes all posting text, and serves files only from `out/`. Binding elsewhere (`--bind`) is for containers whose port is published on localhost and prints a warning; the UI has no login and must never be exposed to a network.
- Settings that choose a file or a program to run (`llm.claude_path`, the company files, `paths`) cannot be changed from the UI.
- The single-page fetch used when adding a posting only reaches public hosts (private, loopback and link-local addresses are refused, redirects are re-checked, size and time are limited).
- API keys live only in environment variables and are never written to files, the database, logs or the UI.
- Your CV's contact details are never sent to an LLM.

Reports about any of these are in scope. Out of scope: attacks that need an attacker already running code as you on your machine, and exposing the UI to a network against the documentation.

## Supported versions

Only the latest commit on the default branch.
