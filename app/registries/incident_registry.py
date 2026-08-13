from app.models.incident import Incident


class IncidentRegistry:
    """
    Keeps track of every Incident currently running (i.e. still open on
    Statuspage) for one bridge. Plain instance state on purpose: a
    class-level list (as Incident used to carry) leaks between bridge
    instances and between tests, which is exactly what this class is meant
    to avoid so the bridge can be reused as a standalone component.
    """

    def __init__(self):
        self.running_incidents: list[Incident] = []

    def is_running(self, incident: Incident) -> bool:
        """
        Method to check if an incident is running or not.

        Arguments:
            incident (Incident): the incident to check
        """
        return incident in self.running_incidents

    def register(self, incident: Incident) -> Incident:
        """
        Register a new running incident.

        Arguments:
            incident (Incident): the Incident to register as currently running
        """

        try:
            self.running_incidents.append(incident)
        except Exception:
            return None
        return incident

    def resolve(self, incident: Incident) -> bool:
        """
        Method to remove an Incident from the running incidents list.

        Arguments:
            incident (Incident) : the incident to remove from the running list
        """

        if not incident or not self.running_incidents or len(self.running_incidents) == 0:
            return False
        if incident not in self.running_incidents:
            return False

        self.running_incidents.remove(incident)
        return True

    def from_component_id(self, component_id: str) -> Incident:
        """
        Get the running incident already open for a given Statuspage
        component ID, if any.

        Arguments:
            component_id (str): the Statuspage component ID
        """

        for incident in self.running_incidents:
            if incident.component_id == component_id:
                return incident
        return None

    def from_id(self, id: str) -> Incident:
        """
        Method to get a running incident by its ID.

        Arguments:
            ID: the ID of the incident to look for
        """

        if not id or len(id) == 0:
            return None

        for incident in self.running_incidents:
            if incident.id == id:
                return incident
        return None
