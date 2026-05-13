# ADR 0001 — Monorepo

**Status:** Accepted
**Date:** 2026-05-13

## Context

Backend (Python pipeline) and clients (Kotlin Multiplatform app) are tightly coupled by one contract: the manifest JSON. Schema drift between two repos is the most common failure mode of split-repo systems.

## Decision

Keep both pieces in a single repository under `backend/` and `client/`, with a top-level `schema/` directory holding the JSON Schema that both sides depend on. CI is path-filtered so backend changes only run Python checks and client changes only run Gradle checks; any change to `schema/**` triggers both.

## Consequences

**Positive**

- Single PR for any schema-affecting change → atomic.
- One issue tracker, one CI config, one release tag.
- Easy onboarding: `git clone` gives the whole system.

**Negative**

- Two heterogeneous toolchains in the same checkout (Python + Gradle).
- Larger clone size.

## Alternatives considered

- **Two repos with a third "schema" repo.** Discarded — the coordination overhead is far worse than the toolchain split.
- **OpenAPI / gRPC service.** Discarded — the backend is not an API, it serves static files; a service contract is overkill.
