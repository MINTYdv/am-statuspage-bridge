from app.models.statuspage_component import StatuspageComponent
from app.registries.component_registry import ComponentRegistry


def registry_with_components():
    registry = ComponentRegistry()
    registry.components = [
        StatuspageComponent("comp-api", "API"),
        StatuspageComponent("comp-db", "Database"),
    ]
    registry.components_groups = [
        StatuspageComponent("group-infra", "Infra", children=[StatuspageComponent("comp-cache", "Cache")]),
    ]
    return registry


def test_get_id_by_name_matches_flat_component_case_insensitive():
    registry = registry_with_components()
    assert registry.get_id_by_name("api") == "comp-api"


def test_get_id_by_name_matches_grouped_component():
    registry = registry_with_components()
    assert registry.get_id_by_name("Infra/Cache") == "comp-cache"


def test_get_id_by_name_returns_none_for_unknown_component():
    registry = registry_with_components()
    assert registry.get_id_by_name("Unknown") is None


def test_get_id_by_name_returns_none_for_unknown_group():
    registry = registry_with_components()
    assert registry.get_id_by_name("Unknown/Cache") is None


def test_load_builds_components_and_groups_from_api(monkeypatch):
    registry = ComponentRegistry()
    client = type("Client", (), {"page_id": "page-1"})()
    client.get_component_groups = lambda: FakeResponse(200, [{"id": "group-infra", "name": "Infra"}])
    client.get_components = lambda: FakeResponse(
        200,
        [
            {"id": "group-infra", "name": "Infra", "group": True},
            {"id": "comp-cache", "name": "Cache", "group": False, "group_id": "group-infra"},
            {"id": "comp-api", "name": "API", "group": False, "group_id": None},
        ],
    )

    assert registry.load(client, "Test Page") is True
    assert registry.get_id_by_name("API") == "comp-api"
    assert registry.get_id_by_name("Infra/Cache") == "comp-cache"


class FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data
        self.text = str(json_data)

    def json(self):
        return self._json_data
