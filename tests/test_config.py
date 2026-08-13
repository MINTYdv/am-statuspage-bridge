from app.config import BridgeConfig


def _config(**overrides):
    defaults = dict(
        statuspage_api_key="key",
        statuspage_page_id="page",
        secret_webhook="secret",
        alertmanager_url="http://alertmanager:9093",
        incidents_store_path="/app/data/incidents_store.json",
        alertmanager_poll_interval_seconds=60,
        log_level="INFO",
    )
    defaults.update(overrides)
    return BridgeConfig(**defaults)


def test_missing_required_vars_empty_when_all_set():
    assert _config().missing_required_vars() == []


def test_missing_required_vars_reports_absent_secret_webhook():
    assert "SECRET_WEBHOOK" in _config(secret_webhook=None).missing_required_vars()


def test_missing_required_vars_reports_absent_statuspage_credentials():
    missing = _config(statuspage_api_key=None, statuspage_page_id=None).missing_required_vars()
    assert "STATUSPAGE_API_KEY" in missing
    assert "STATUSPAGE_PAGE_ID" in missing


def test_from_env_has_no_hardcoded_webhook_secret(monkeypatch):
    monkeypatch.delenv("SECRET_WEBHOOK", raising=False)
    config = BridgeConfig.from_env()
    assert not config.secret_webhook
    assert "SECRET_WEBHOOK" in config.missing_required_vars()
