# ADR 0002 — No Python web framework

**Status:** Accepted
**Date:** 2026-05-13

## Context

The backend produces a `manifest.json` and a directory of PNG tiles. Clients fetch both over HTTPS. A web framework would let us authenticate, rate-limit, and serve files. So would Caddy alone.

## Decision

Use Caddy as the only HTTP-facing component. Python writes files; Caddy serves them. No FastAPI / Flask / aiohttp / Starlette.

## Consequences

**Positive**

- One fewer long-running process to babysit. The pipeline is a set of one-shot CLI scripts triggered by systemd timers — easy to reason about, easy to retry.
- Static-file serving in Caddy is fast and battle-tested.
- Auth (`basic_auth`) and rate limiting (`rate_limit` module) are configured declaratively in one file.
- TLS, HTTP/2, compression, and ACME come for free.

**Negative**

- Anything that needs a request context (per-user customisation, dynamic responses) must move into the client or be precomputed.
- Atomic-write discipline matters: the pipeline must never expose a half-written `manifest.json`. Mitigated by always writing to `*.tmp` then `os.replace`.

## Alternatives considered

- **FastAPI in front of the same files.** Discarded — adds a process and concurrency model we don't need.
- **Nginx instead of Caddy.** Plausible; Caddy wins on automatic HTTPS and a much simpler Caddyfile.
