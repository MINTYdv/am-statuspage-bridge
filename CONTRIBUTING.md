# Contributing

Contributions are welcome. This project is intentionally small, so please keep
changes focused and avoid adding dependencies or abstractions unless they solve
a real problem.

## Development setup

```bash
git clone https://github.com/MINTYdv/am-statuspage-bridge.git
cd am-statuspage-bridge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Copy `.env.example` to `.env` and fill in a Statuspage test page's credentials
(or run against mocks, see `tests/`).

## Running the bridge locally

```bash
uvicorn statuspage_bridge:app --reload --port 9090
```

## Tests and linting

```bash
pytest
ruff check .
ruff format --check .
```

Run `ruff format .` to auto-fix formatting before committing.

## Making a change

1. Open an issue first for anything beyond a small fix, so we can agree on the
   approach before you spend time on it.
2. Add or update tests for any behavior change, especially around alert
   handling, grouping, or incident lifecycle.
3. Keep commits focused; one logical change per PR.
4. Make sure `pytest` and `ruff` both pass before opening the PR.

## Reporting bugs

Open an issue with the alert payload (or labels) that triggered the problem and
the relevant bridge logs. Redact `STATUSPAGE_API_KEY`, `SECRET_WEBHOOK`, and any
other secret before posting.

For security issues, see [SECURITY.md](SECURITY.md) instead of opening a public issue.
