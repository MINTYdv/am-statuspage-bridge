# Security policy

## Reporting a vulnerability

If you find a security issue in this project, please open a private report through
[GitHub Security Advisories](../../security/advisories/new) instead of a public issue.
Include:

- A description of the issue and its impact.
- Steps to reproduce, or a proof of concept if applicable.
- The version/commit you tested against.

You should get an initial response within a few days.

## Supported versions

This project does not yet maintain multiple release branches. Security fixes are
applied to the `main` branch; run the latest version.

## Scope

Things we consider in scope:

- Authentication bypass on the `/webhook` endpoint.
- Any way for a webhook request to make the bridge act on a different Statuspage
  page/component than configured, or leak the configured secrets.
- Injection issues in how alert data is turned into Statuspage API calls.

Things that are expected behavior, not vulnerabilities:

- The bridge trusts whatever `ALERTMANAGER_URL` and Statuspage credentials it is
  configured with; it is meant to run in a trusted network next to AlertManager,
  not to be exposed directly to the public internet without your own reverse
  proxy / network controls in front of it.
- Denial of service through a flood of webhook requests: put a reverse proxy or
  rate limiter in front of the bridge if it's reachable from an untrusted network.

## Hardening notes for operators

- Always set `SECRET_WEBHOOK` to a long random value (`openssl rand -hex 32`).
  The bridge refuses to start without it.
- Prefer passing the webhook token via the `Authorization: Bearer <token>` header
  over the `?token=` query parameter, so it doesn't end up in access logs.
- Run the container as the provided non-root user (the default).
- Keep `STATUSPAGE_API_KEY` out of version control; use `.env` (gitignored) or
  your orchestrator's secret store.
