# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

Nothing yet.

## [1.0.0] - 2026-08-13

First public release.

### Features
- Receives AlertManager webhook notifications (`firing` and `resolved`) on `POST /webhook`.
- Creates a Statuspage incident automatically when an alert fires, resolved to a component by name (including `Group/Component` syntax).
- Groups concurrent alerts on the same component into a single incident, escalating severity when a second independent alert stacks onto an already-open one.
- Resolves incidents automatically once all their alerts have cleared, whether partially (one alert among several) or fully (the last one).
- Derives the Statuspage incident impact (minor/major/critical) from the alert's component status instead of a fixed value.
- Persists running incidents to a local JSON file (atomic write) so state survives a bridge restart.
- Periodically reconciles running incidents against AlertManager's active alerts, so an incident doesn't stay open forever if a `resolved` webhook is lost.
- Fails fast at startup on missing configuration or an unreachable Statuspage API, instead of serving traffic in a broken state.
- `GET /health` reflects real startup readiness; `POST /webhook` accepts the shared secret via `?token=` or `Authorization: Bearer`, compared with `hmac.compare_digest`.
- Docker image runs as a non-root user, with a `HEALTHCHECK` and exec-form `CMD` for proper signal handling on `docker stop`.
- Test suite (pytest) and CI (lint, format check, tests, dependency audit, Docker build) via GitHub Actions.

### Known limitations
- Single-instance only: incident state lives in process memory and a local file. Running more than one replica/worker against the same `INCIDENTS_STORE_PATH` is not supported and can create duplicate incidents.
- No internal retry/backoff for outbound Statuspage API calls; the bridge relies on AlertManager's own webhook redelivery on failure.
- The bridge only manages incidents it created itself; it cannot detect or take over an incident created manually on Statuspage for the same component.
