from app.models.alert_component import ComponentStatus

# Statuspage incident "impact" (the severity badge shown on the public page)
# is a separate field from a component's own status. This maps the
# component-level ComponentStatus driving an incident to the closest
# Statuspage impact level, so the badge reflects the alert's real severity
# instead of being fixed at "critical" for every incident.
IMPACT_BY_COMPONENT_STATUS = {
    ComponentStatus.MAJOR_OUTAGE: "critical",
    ComponentStatus.PARTIAL_OUTAGE: "major",
    ComponentStatus.DEGRADED_PERFORMANCE: "minor",
    ComponentStatus.UNDER_MAINTENANCE: "minor",
    ComponentStatus.OPERATIONAL: "none",
    ComponentStatus.NO_UPDATE: "minor",
}


class IncidentEntry:
    """
    A single alert currently contributing to a running Incident.
    Rendered as one bullet point in the Statuspage incident body.
    """

    def __init__(self, alert_name: str, description: str, status: ComponentStatus, notify: bool):
        self.alert_name = alert_name
        self.description = description
        self.status = status
        self.notify = notify

    def to_dict(self) -> dict:
        return {"alert_name": self.alert_name, "description": self.description, "status": self.status.value, "notify": self.notify}

    @classmethod
    def from_dict(cls, data: dict) -> "IncidentEntry":
        return cls(alert_name=data["alert_name"], description=data["description"], status=ComponentStatus(data["status"]), notify=data["notify"])


class Incident:
    """
    Represents a running Statuspage incident for a single component.
    Several alerts can stack onto the same Incident when they target the same
    component: each alert contributes one IncidentEntry (one bullet point in
    the incident body), and the incident stays open as long as at least one
    entry remains.

    An alert that targets several components (statuspage_components with
    multiple names) is NOT tied to a single shared Incident: it contributes
    its own entry independently to each targeted component's Incident (one
    per component, created/updated/closed on its own), the same way it would
    if it were several separate single-component alerts.
    """

    def __init__(self, id: str, component_id: str, title: str):
        self.id = id
        self.component_id = component_id
        self.title = title
        self.status = ComponentStatus.PARTIAL_OUTAGE
        self.entries: dict[str, IncidentEntry] = {}

    def add_entry(self, alert_name: str, description: str, status: ComponentStatus, notify: bool):
        """
        Attach an alert to this incident (or refresh it, if it was already attached).

        - The first alert ever attached to the incident drives its initial severity.
        - Any additional, genuinely new alert stacking onto an already-running
          incident escalates it to MAJOR_OUTAGE (several concurrent problems on
          the same component are worse than a single one). An incident already
          at MAJOR_OUTAGE simply stays there.
        - Re-attaching an alert that was already tracked (Alertmanager resending
          a "firing" notification) is a no-op for severity purposes.
        """

        is_new_alert = alert_name not in self.entries
        self.entries[alert_name] = IncidentEntry(alert_name, description, status, notify)

        if len(self.entries) == 1:
            self.status = status
        elif is_new_alert:
            self.status = ComponentStatus.MAJOR_OUTAGE

    def remove_entry(self, alert_name: str):
        """
        Detach a resolved alert from this incident. The incident's severity is
        never downgraded automatically: once escalated to MAJOR_OUTAGE it stays
        there until every entry has resolved and the incident is closed.
        """
        self.entries.pop(alert_name, None)

    def is_empty(self) -> bool:
        return len(self.entries) == 0

    def get_body(self) -> str:
        """
        Render the incident body as one bullet point per active alert.
        """
        if not self.entries:
            return ""
        return "\n".join(f"- {entry.description}" for entry in self.entries.values())

    def get_impact(self) -> str:
        """
        Statuspage "impact_override" value matching this incident's current
        severity, so the public page badge tracks the underlying alert
        severity instead of staying fixed at whatever it was created with.
        """
        return IMPACT_BY_COMPONENT_STATUS.get(self.status, "minor")

    def get_components_payload(self, forced_status: ComponentStatus = None) -> dict:
        """
        JSON payload content for the "components" field of the Statuspage API payload.
        """
        status = forced_status or self.status
        return {self.component_id: status}

    def to_dict(self) -> dict:
        """
        Serialize this Incident for local persistence, so it can be restored
        by from_dict() after a restart.
        """
        return {
            "id": self.id,
            "component_id": self.component_id,
            "title": self.title,
            "status": self.status.value,
            "entries": {name: entry.to_dict() for name, entry in self.entries.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Incident":
        """
        Rebuild an Incident previously serialized with to_dict(), as read
        back from the local incidents store.
        """
        incident = cls(id=data["id"], component_id=data["component_id"], title=data["title"])
        incident.status = ComponentStatus(data["status"])
        incident.entries = {name: IncidentEntry.from_dict(entry_data) for name, entry_data in data.get("entries", {}).items()}
        return incident
