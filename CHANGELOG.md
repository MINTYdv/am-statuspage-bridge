# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Test suite covering incident creation, stacking/escalation, resolution, grouping, reconciliation, and persistence.
- GitHub Actions CI (lint, format check, tests, dependency audit, Docker build).
- `docker-compose.yml` with a persistent named volume for the incidents store.
- `.env.example`, `SECURITY.md`, `CONTRIBUTING.md`, issue/PR templates.
- Support for the webhook token via `Authorization: Bearer <token>` header, in addition to the `?token=` query parameter.
- Real `/health` readiness check reflecting whether the bridge finished startup.

### Changed
- Statuspage incident `impact_override` is now derived from the alert's component status (minor/major/critical) instead of always being `"critical"`.
- The bridge now fails fast at startup (instead of starting in a broken state) when required configuration is missing or the Statuspage API is unreachable.
- Docker image now runs as a non-root user and uses exec-form `CMD` for proper signal handling on `docker stop`.
- Dependencies are now pinned.

### Removed
- The insecure default value for `SECRET_WEBHOOK` (`SuperSecureSecret`). The variable is now required.

### Security
- Webhook token comparison now uses a constant-time comparison (`hmac.compare_digest`).
