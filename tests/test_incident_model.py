from app.models.alert_component import ComponentStatus
from app.models.incident import Incident


def test_first_entry_sets_initial_severity():
    incident = Incident(id="inc-1", component_id="comp-1", title="API down")
    incident.add_entry("AlertA", "desc", ComponentStatus.DEGRADED_PERFORMANCE, True)

    assert incident.status == ComponentStatus.DEGRADED_PERFORMANCE
    assert incident.get_impact() == "minor"


def test_second_distinct_alert_escalates_to_major_outage():
    incident = Incident(id="inc-1", component_id="comp-1", title="API down")
    incident.add_entry("AlertA", "desc", ComponentStatus.DEGRADED_PERFORMANCE, True)
    incident.add_entry("AlertB", "desc", ComponentStatus.PARTIAL_OUTAGE, True)

    assert incident.status == ComponentStatus.MAJOR_OUTAGE
    assert incident.get_impact() == "critical"
    assert len(incident.entries) == 2


def test_reattaching_same_alert_does_not_escalate():
    incident = Incident(id="inc-1", component_id="comp-1", title="API down")
    incident.add_entry("AlertA", "desc", ComponentStatus.DEGRADED_PERFORMANCE, True)
    incident.add_entry("AlertA", "desc updated", ComponentStatus.DEGRADED_PERFORMANCE, True)

    assert incident.status == ComponentStatus.DEGRADED_PERFORMANCE
    assert len(incident.entries) == 1


def test_escalation_is_never_downgraded_on_partial_resolve():
    incident = Incident(id="inc-1", component_id="comp-1", title="API down")
    incident.add_entry("AlertA", "desc", ComponentStatus.DEGRADED_PERFORMANCE, True)
    incident.add_entry("AlertB", "desc", ComponentStatus.PARTIAL_OUTAGE, True)
    incident.remove_entry("AlertB")

    assert incident.status == ComponentStatus.MAJOR_OUTAGE
    assert not incident.is_empty()


def test_incident_is_empty_after_all_entries_resolved():
    incident = Incident(id="inc-1", component_id="comp-1", title="API down")
    incident.add_entry("AlertA", "desc", ComponentStatus.DEGRADED_PERFORMANCE, True)
    incident.remove_entry("AlertA")

    assert incident.is_empty()


def test_to_dict_from_dict_round_trip():
    incident = Incident(id="inc-1", component_id="comp-1", title="API down")
    incident.add_entry("AlertA", "desc", ComponentStatus.DEGRADED_PERFORMANCE, True)
    incident.add_entry("AlertB", "desc2", ComponentStatus.PARTIAL_OUTAGE, False)

    restored = Incident.from_dict(incident.to_dict())

    assert restored.id == incident.id
    assert restored.component_id == incident.component_id
    assert restored.status == incident.status
    assert set(restored.entries) == {"AlertA", "AlertB"}
    assert restored.entries["AlertB"].notify is False
