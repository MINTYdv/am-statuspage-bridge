import json
import logging
import os
import tempfile

from app.models.incident import Incident

logger = logging.getLogger("statuspage_bridge")


class IncidentStore:
    """
    Persists the list of currently running Incidents to a local JSON file, so
    Incident.running_incidents can be restored after a restart of the bridge
    instead of starting from an empty state (which would otherwise make the
    bridge blind to incidents it already opened on Statuspage).
    """

    def __init__(self, path: str):
        self.path = path

    def load(self) -> list[Incident]:
        """
        Load previously persisted incidents from disk.
        Returns an empty list if the store does not exist yet, or if its
        content cannot be parsed.
        """
        if not os.path.exists(self.path):
            logger.info(f"No incidents store found at '{self.path}'; starting with an empty incident list.")
            return []

        try:
            with open(self.path, "r") as f:
                raw_incidents = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Could not read incidents store at '{self.path}': {e}. Starting with an empty incident list.")
            return []

        incidents = []
        for raw_incident in raw_incidents:
            try:
                incidents.append(Incident.from_dict(raw_incident))
            except (KeyError, ValueError) as e:
                logger.error(f"Skipping corrupted incident entry in local store: {e}")

        logger.info(f"Loaded {len(incidents)} running incident(s) from local store '{self.path}'.")
        return incidents

    def save(self, incidents: list[Incident]):
        """
        Persist the given incidents to disk, replacing any previous content.
        Writes to a temporary file first and atomically renames it, so a
        crash mid-write never leaves a corrupted store behind.
        """
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)

        data = [incident.to_dict() for incident in incidents]

        fd, tmp_path = tempfile.mkstemp(dir=directory)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.path)
        except OSError as e:
            logger.error(f"Failed to persist incidents store to '{self.path}': {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
