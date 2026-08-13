import importlib
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeResponse, make_alert


@pytest.fixture
def bridge_env(tmp_path, monkeypatch):
    monkeypatch.setenv("STATUSPAGE_API_KEY", "test-api-key")
    monkeypatch.setenv("STATUSPAGE_PAGE_ID", "test-page-id")
    monkeypatch.setenv("SECRET_WEBHOOK", "test-secret")
    monkeypatch.setenv("ALERTMANAGER_URL", "http://alertmanager.test:9093")
    monkeypatch.setenv("INCIDENTS_STORE_PATH", str(tmp_path / "incidents_store.json"))
    monkeypatch.setenv("ALERTMANAGER_POLL_INTERVAL_SECONDS", "3600")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


@pytest.fixture
def app_client(bridge_env):
    """
    Reloads statuspage_bridge with the env above so its module-level
    `config`/`bridge` singletons pick up test settings, wires the bridge's
    HTTP clients to mocks that simulate a healthy Statuspage/Alertmanager,
    then drives the real FastAPI lifespan (startup + shutdown) through
    TestClient.
    """
    import statuspage_bridge as mod

    importlib.reload(mod)

    mod.bridge.statuspage_client = Mock()
    mod.bridge.statuspage_client.get_page.return_value = FakeResponse(200, {"name": "Test Status Page"})
    mod.bridge.statuspage_client.get_component_groups.return_value = FakeResponse(200, [])
    mod.bridge.statuspage_client.get_components.return_value = FakeResponse(
        200,
        [
            {"id": "comp-api", "name": "API", "group": False, "group_id": None},
        ],
    )
    mod.bridge.alertmanager_client = Mock()
    mod.bridge.alertmanager_client.get_active_alertnames.return_value = set()

    with TestClient(mod.app) as client:
        yield client, mod


def test_health_ok_once_ready(app_client):
    client, _ = app_client
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_health_returns_503_before_startup(bridge_env):
    """
    A freshly constructed bridge is not ready until StatuspageBridge.startup()
    completes; the health route must reflect that instead of always saying
    "healthy" (health_check() itself makes no network call, so this needs no
    mocking of the Statuspage/Alertmanager clients).
    """
    import asyncio

    import statuspage_bridge as mod

    importlib.reload(mod)

    assert mod.bridge.ready is False
    with pytest.raises(mod.HTTPException) as exc_info:
        asyncio.run(mod.health_check())
    assert exc_info.value.status_code == 503


def test_webhook_requires_token(app_client):
    client, _ = app_client
    resp = client.post("/webhook", json={"alerts": []})
    assert resp.status_code == 401


def test_webhook_rejects_wrong_token(app_client):
    client, _ = app_client
    resp = client.post("/webhook?token=wrong-token", json={"alerts": []})
    assert resp.status_code == 401


def test_webhook_accepts_bearer_header(app_client):
    client, _ = app_client
    resp = client.post("/webhook", json={"alerts": []}, headers={"Authorization": "Bearer test-secret"})
    assert resp.status_code == 200


def test_webhook_with_no_alerts_is_ignored(app_client):
    client, _ = app_client
    resp = client.post("/webhook?token=test-secret", json={"alerts": []})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_rejects_malformed_json(app_client):
    client, _ = app_client
    resp = client.post(
        "/webhook?token=test-secret",
        content=b"not json",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400


def test_webhook_firing_alert_creates_incident(app_client):
    client, mod = app_client
    mod.bridge.statuspage_client.create_incident.return_value = FakeResponse(201, {"id": "inc-1"})

    payload = {"alerts": [make_alert("HighErrorRate", "firing", "API", "major_outage")]}
    resp = client.post("/webhook?token=test-secret", json=payload)

    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
    assert mod.bridge.incident_registry.from_component_id("comp-api") is not None


def test_webhook_returns_500_on_statuspage_failure(app_client):
    client, mod = app_client
    mod.bridge.statuspage_client.create_incident.return_value = FakeResponse(500, text="boom")

    payload = {"alerts": [make_alert("HighErrorRate", "firing", "API", "major_outage")]}
    resp = client.post("/webhook?token=test-secret", json=payload)

    assert resp.status_code == 500
