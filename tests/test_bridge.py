import pytest

from tests.conftest import FakeResponse, make_alert


def test_firing_alert_creates_incident(bridge):
    bridge.statuspage_client.create_incident.return_value = FakeResponse(201, {"id": "inc-1"})

    bridge.process_alert(make_alert("HighErrorRate", "firing", "API", "major_outage"))

    bridge.statuspage_client.create_incident.assert_called_once()
    incident = bridge.incident_registry.from_component_id("comp-api")
    assert incident is not None
    assert incident.id == "inc-1"
    payload = bridge.statuspage_client.create_incident.call_args[0][0]
    assert payload["incident"]["impact_override"] == "critical"


def test_repeated_firing_of_same_alert_is_idempotent(bridge):
    bridge.statuspage_client.create_incident.return_value = FakeResponse(201, {"id": "inc-1"})
    bridge.statuspage_client.update_incident.return_value = FakeResponse(200)

    alert = make_alert("HighErrorRate", "firing", "API", "major_outage")
    bridge.process_alert(alert)
    bridge.process_alert(alert)

    bridge.statuspage_client.create_incident.assert_called_once()
    assert bridge.statuspage_client.update_incident.call_count == 1  # second firing stacks as a no-op update
    assert len(bridge.incident_registry.running_incidents) == 1
    incident = bridge.incident_registry.from_component_id("comp-api")
    assert len(incident.entries) == 1


def test_second_distinct_alert_stacks_and_escalates(bridge):
    bridge.statuspage_client.create_incident.return_value = FakeResponse(201, {"id": "inc-1"})
    bridge.statuspage_client.update_incident.return_value = FakeResponse(200)

    bridge.process_alert(make_alert("HighErrorRate", "firing", "API", "degraded_performance"))
    bridge.process_alert(make_alert("HighLatency", "firing", "API", "partial_outage"))

    incident = bridge.incident_registry.from_component_id("comp-api")
    assert len(incident.entries) == 2
    assert incident.status.value == "major_outage"
    payload = bridge.statuspage_client.update_incident.call_args[0][1]
    assert payload["incident"]["impact_override"] == "critical"


def test_resolved_alert_closes_incident_when_last_entry(bridge):
    bridge.statuspage_client.create_incident.return_value = FakeResponse(201, {"id": "inc-1"})
    bridge.statuspage_client.update_incident.return_value = FakeResponse(200)

    bridge.process_alert(make_alert("HighErrorRate", "firing", "API", "major_outage"))
    bridge.process_alert(make_alert("HighErrorRate", "resolved", "API", "major_outage"))

    assert bridge.incident_registry.from_component_id("comp-api") is None
    resolve_payload = bridge.statuspage_client.update_incident.call_args[0][1]
    assert resolve_payload["incident"]["status"] == "resolved"


def test_resolved_alert_keeps_incident_open_if_others_still_active(bridge):
    bridge.statuspage_client.create_incident.return_value = FakeResponse(201, {"id": "inc-1"})
    bridge.statuspage_client.update_incident.return_value = FakeResponse(200)

    bridge.process_alert(make_alert("HighErrorRate", "firing", "API", "degraded_performance"))
    bridge.process_alert(make_alert("HighLatency", "firing", "API", "partial_outage"))
    bridge.process_alert(make_alert("HighLatency", "resolved", "API", "partial_outage"))

    incident = bridge.incident_registry.from_component_id("comp-api")
    assert incident is not None
    assert len(incident.entries) == 1
    assert "HighErrorRate" in incident.entries


def test_resolved_alert_with_no_running_incident_is_ignored(bridge):
    bridge.process_alert(make_alert("Ghost", "resolved", "API", "major_outage"))

    bridge.statuspage_client.update_incident.assert_not_called()


def test_multi_component_alert_creates_independent_incidents(bridge):
    bridge.statuspage_client.create_incident.return_value = FakeResponse(201, {"id": "inc-1"})

    bridge.process_alert(make_alert("Outage", "firing", "API;Database", "major_outage;major_outage"))

    assert len(bridge.incident_registry.running_incidents) == 2
    assert bridge.statuspage_client.create_incident.call_count == 2


def test_alert_with_unknown_component_is_skipped(bridge):
    bridge.process_alert(make_alert("Outage", "firing", "Unknown", "major_outage"))

    bridge.statuspage_client.create_incident.assert_not_called()
    assert bridge.incident_registry.running_incidents == []


def test_create_incident_failure_raises_and_does_not_register(bridge):
    bridge.statuspage_client.create_incident.return_value = FakeResponse(500, text="boom")

    with pytest.raises(RuntimeError):
        bridge.process_alert(make_alert("HighErrorRate", "firing", "API", "major_outage"))

    assert bridge.incident_registry.running_incidents == []


def test_resolve_failure_keeps_entry_for_retry(bridge):
    bridge.statuspage_client.create_incident.return_value = FakeResponse(201, {"id": "inc-1"})
    bridge.statuspage_client.update_incident.return_value = FakeResponse(500, text="boom")

    bridge.process_alert(make_alert("HighErrorRate", "firing", "API", "major_outage"))
    with pytest.raises(RuntimeError):
        bridge.process_alert(make_alert("HighErrorRate", "resolved", "API", "major_outage"))

    incident = bridge.incident_registry.from_component_id("comp-api")
    assert incident is not None
    assert "HighErrorRate" in incident.entries


def test_persisted_incidents_survive_a_restart(bridge, tmp_path):
    bridge.statuspage_client.create_incident.return_value = FakeResponse(201, {"id": "inc-1"})
    bridge.process_alert(make_alert("HighErrorRate", "firing", "API", "major_outage"))

    from app.bridge import StatuspageBridge

    restarted = StatuspageBridge(bridge.config)
    restarted.incident_registry.running_incidents = restarted.incident_store.load()

    incident = restarted.incident_registry.from_component_id("comp-api")
    assert incident is not None
    assert incident.id == "inc-1"


def test_reconcile_resolves_alerts_no_longer_firing_on_alertmanager(bridge):
    bridge.statuspage_client.create_incident.return_value = FakeResponse(201, {"id": "inc-1"})
    bridge.statuspage_client.update_incident.return_value = FakeResponse(200)
    bridge.process_alert(make_alert("HighErrorRate", "firing", "API", "major_outage"))

    bridge.alertmanager_client.get_active_alertnames.return_value = set()  # AM no longer reports it

    bridge.reconcile_with_alertmanager()

    assert bridge.incident_registry.from_component_id("comp-api") is None


def test_reconcile_skips_when_alertmanager_unreachable(bridge):
    bridge.statuspage_client.create_incident.return_value = FakeResponse(201, {"id": "inc-1"})
    bridge.process_alert(make_alert("HighErrorRate", "firing", "API", "major_outage"))

    bridge.alertmanager_client.get_active_alertnames.return_value = None  # unreachable

    bridge.reconcile_with_alertmanager()

    incident = bridge.incident_registry.from_component_id("comp-api")
    assert incident is not None
    assert "HighErrorRate" in incident.entries
