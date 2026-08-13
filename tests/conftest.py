from unittest.mock import Mock

import pytest

from app.bridge import StatuspageBridge
from app.config import BridgeConfig
from app.models.statuspage_component import StatuspageComponent


class FakeResponse:
    """
    Minimal stand-in for requests.Response, just enough for the bridge's
    status_code / json() / text usage.
    """

    def __init__(self, status_code, json_data=None, text=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text if text is not None else str(self._json_data)

    def json(self):
        return self._json_data


def make_alert(alertname, status, components, statuses, title="{alertname}", notify="true", description="something broke"):
    return {
        "status": status,
        "labels": {
            "alertname": alertname,
            "statuspage_components": components,
            "statuspage_status": statuses,
            "statuspage_title": title,
            "statuspage_notify": notify,
        },
        "annotations": {"description": description},
    }


@pytest.fixture
def bridge(tmp_path):
    """
    A StatuspageBridge wired with mocked Statuspage/Alertmanager HTTP
    clients and a component registry preloaded with a flat component and a
    grouped one, so tests can exercise process_alert() and friends without
    any real network call. Persistence still goes through a real
    IncidentStore pointed at a temp file, so store round-trips are exercised
    for real.
    """
    config = BridgeConfig(
        statuspage_api_key="test-api-key",
        statuspage_page_id="test-page-id",
        secret_webhook="test-secret",
        alertmanager_url="http://alertmanager.test:9093",
        incidents_store_path=str(tmp_path / "incidents_store.json"),
        alertmanager_poll_interval_seconds=3600,
        log_level="DEBUG",
    )
    b = StatuspageBridge(config)
    b.statuspage_client = Mock()
    b.alertmanager_client = Mock()
    b.ready = True

    b.component_registry.components = [
        StatuspageComponent("comp-api", "API"),
        StatuspageComponent("comp-db", "Database"),
    ]
    group = StatuspageComponent("group-infra", "Infra", children=[StatuspageComponent("comp-cache", "Cache")])
    b.component_registry.components_groups = [group]

    return b
