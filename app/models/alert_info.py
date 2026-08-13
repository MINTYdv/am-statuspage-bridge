import datetime
import logging

from app.models.alert_component import AlertComponent, ComponentStatus
from app.registries.component_registry import ComponentRegistry
from app.utils.config_helper import ConfigHelper

logger = logging.getLogger("statuspage_bridge")


class AlertInfo:
    def __init__(self, alert_name: str, components: list[AlertComponent], notify: bool, title: str):
        self.alert_name = alert_name
        self.components = components
        self.notify = notify
        self.title = title

    @classmethod
    def from_labels(cls, alert_name: str, labels: dict, component_registry: ComponentRegistry) -> "AlertInfo":
        """
        Extracts structured information from the Prometheus alert labels.

        Reads 'statuspage_components', 'statuspage_status', 'statuspage_notify',
        and 'statuspage_title' to build an AlertInfo object.
        """
        raw_components = labels.get("statuspage_components")
        raw_status = labels.get("statuspage_status")
        raw_title = labels.get("statuspage_title")
        raw_notify = labels.get("statuspage_notify", "true").lower()

        if not all([raw_components, raw_status, raw_title]):
            raise ValueError(f"Missing required statuspage labels in alert '{alert_name}'. Got components={raw_components}, status={raw_status}, title={raw_title}")

        # Support multiple semicolon-separated values if needed (matches your existing model logic)
        raw_names = raw_components.split(";")
        raw_statuses = raw_status.split(";")

        if len(raw_names) != len(raw_statuses):
            raise ValueError("The amount of component names does not match the amount of statuses.")

        alert_components = []
        for comp_name, status_str in zip(raw_names, raw_statuses):
            comp_id = component_registry.get_id_by_name(comp_name)

            if not comp_id:
                logger.error(f"Component with name '{comp_name}' not found on Statuspage.")
                continue

            try:
                status_enum = ComponentStatus(status_str.lower())
            except ValueError:
                logger.error(f"Incorrect component status provided: '{status_str}' for component '{comp_name}'.")
                continue

            alert_components.append(AlertComponent(comp_id, status_enum))

        notify_bool = ConfigHelper.parse_bool(raw_notify)

        return cls(alert_name, alert_components, notify_bool, raw_title)

    def get_title(self) -> str:
        """
        Return the formatted title of the Alert, that will be in the Incident description.
        Compatible with placeholders.
        """
        return self.get_formatted_string(self.title) or None

    def get_formatted_string(self, source: str) -> str:
        """
        Format a string by replacing simple placeholders.

        {date} = today's date
        """

        if not source or len(source) == 0:
            return None

        res = source
        # Manage different placeholders
        if "{date}" in source.lower():
            now = datetime.datetime.now()
            formatted_date = now.strftime("%d/%m/%Y %H:%M:%S")
            res = source.replace("{date}", formatted_date)

        return res

    def get_components_id(self) -> list[str]:
        """
        Get a list of all the components StatusPage IDs
        """

        res = []
        for c in self.components:
            res.append(c.id)
        return res
