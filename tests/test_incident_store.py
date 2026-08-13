import json

from app.models.alert_component import ComponentStatus
from app.models.incident import Incident
from app.storage.incident_store import IncidentStore


def test_load_returns_empty_list_when_store_missing(tmp_path):
    store = IncidentStore(str(tmp_path / "missing.json"))
    assert store.load() == []


def test_save_then_load_round_trip(tmp_path):
    store = IncidentStore(str(tmp_path / "nested" / "incidents.json"))
    incident = Incident(id="inc-1", component_id="comp-1", title="API down")
    incident.add_entry("AlertA", "desc", ComponentStatus.MAJOR_OUTAGE, True)

    store.save([incident])
    restored = store.load()

    assert len(restored) == 1
    assert restored[0].id == "inc-1"
    assert restored[0].status == ComponentStatus.MAJOR_OUTAGE


def test_load_skips_corrupted_entries(tmp_path):
    path = tmp_path / "incidents.json"
    path.write_text(json.dumps([{"id": "inc-1"}]))  # missing required keys

    store = IncidentStore(str(path))
    assert store.load() == []


def test_load_returns_empty_list_on_invalid_json(tmp_path):
    path = tmp_path / "incidents.json"
    path.write_text("not json")

    store = IncidentStore(str(path))
    assert store.load() == []


def test_save_does_not_leave_tmp_file_behind(tmp_path):
    store = IncidentStore(str(tmp_path / "incidents.json"))
    store.save([])

    leftovers = [p for p in tmp_path.iterdir() if p.name != "incidents.json"]
    assert leftovers == []
