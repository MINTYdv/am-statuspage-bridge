import logging

from app.clients.alertmanager_client import AlertmanagerClient
from app.clients.statuspage_client import StatuspageClient
from app.config import BridgeConfig
from app.models.alert_component import ComponentStatus
from app.models.alert_info import AlertInfo
from app.models.incident import Incident
from app.registries.component_registry import ComponentRegistry
from app.registries.incident_registry import IncidentRegistry
from app.storage.incident_store import IncidentStore

logger = logging.getLogger("statuspage_bridge")


class StatuspageBridge:
    """
    Core of the bridge, kept independent from FastAPI on purpose: it turns
    Alertmanager alerts into Statuspage incidents (and back), and keeps that
    state consistent across restarts and missed webhooks. Everything
    HTTP-framework-specific stays out of this class, so it can be dropped
    into another project as a plain library object (build a BridgeConfig,
    instantiate a StatuspageBridge, call startup(), feed it alerts).
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.statuspage_client = StatuspageClient(config.statuspage_api_key, config.statuspage_page_id)
        self.alertmanager_client = AlertmanagerClient(config.alertmanager_url)
        self.incident_store = IncidentStore(config.incidents_store_path)
        self.component_registry = ComponentRegistry()
        self.incident_registry = IncidentRegistry()
        self.page_name = "UNKNOWN_PAGE"
        self.ready = False

    def startup(self):
        """
        Method to run everything the bridge needs before it can start
        serving webhooks: validate the Statuspage credentials, load the
        components tree, restore the incidents that were running before a
        possible restart, and catch up with whatever resolved while it was
        down.

        Raises RuntimeError if required configuration is missing or the
        Statuspage API is not reachable, so the process fails fast at
        startup instead of serving traffic behind a "healthy" check while
        actually unable to do its job.
        """
        missing_vars = self.config.missing_required_vars()
        if missing_vars:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")

        if not self.check_statuspage_connection():
            raise RuntimeError("Could not connect to the Statuspage API; check STATUSPAGE_API_KEY and STATUSPAGE_PAGE_ID.")

        if not self.component_registry.load(self.statuspage_client, self.page_name):
            raise RuntimeError("Could not load components from the Statuspage API.")

        self.incident_registry.running_incidents = self.incident_store.load()

        # Catch up on anything that resolved while the bridge was down, before we start responding to webhooks again
        self.reconcile_with_alertmanager()

        self.ready = True

    def check_statuspage_connection(self) -> bool:
        """
        Method to check if the Statuspage API is reachable and if the provided API key is valid.
        This can be used as a health check for the application.
        """
        response = self.statuspage_client.get_page()
        if response.status_code == 200:
            # extract the statuspage public name
            page_data = response.json()
            self.page_name = page_data.get("name")
            logger.info(f"Successfully connected to Statuspage API and verified page '{self.page_name}' (ID: {self.config.statuspage_page_id}).")
            return True
        else:
            logger.error(f"Failed to connect to Statuspage API: {response.text}")
            return False

    def persist_incidents(self):
        """
        Save the current state of the incident registry to the local store,
        so it survives after restart of the bridge
        """
        self.incident_store.save(self.incident_registry.running_incidents)

    def process_alert(self, alert: dict):
        """
        Process a single Alertmanager alert: extract its Statuspage labels,
        then create, update or resolve the Incident(s) it targets depending
        on whether it is firing or resolved.

        An alert can target several components at once (statuspage_components
        with multiple names). Incidents are tracked per single component, so
        such an alert contributes its own entry independently to each of
        them: one incident created/updated/closed per component, exactly as
        if it were several separate alerts.

        Raises RuntimeError if a Statuspage API call failed while processing
        one of the targeted components, so the caller (the webhook route)
        can turn it into the appropriate HTTP error.
        """
        labels = alert.get("labels", {})
        alert_name = labels.get("alertname", "Unknown Alert")

        try:
            alert_info = AlertInfo.from_labels(alert_name, labels, self.component_registry)
        except ValueError as e:
            logger.error(f"Error extracting statuspage labels from {alert_name}: {e}")
            return

        if not alert_info:
            logger.error(f"Could not extract alert info for alert {alert_name}. Skipping this alert.")
            return

        status = alert.get("status")  # "firing" ou "resolved"
        description = alert.get("annotations", {}).get("description", "No description provided.")

        if not alert_info.components:
            logger.warning(f"Alert {alert_name} did not resolve to any known Statuspage component. Skipping this alert.")
            return

        logger.info(f"Received alert {alert_name} with status {status}.")

        for comp in alert_info.components:
            incident = self.incident_registry.from_component_id(comp.id)

            if status == "firing":
                self._handle_firing_alert(comp, incident, alert_name, description, alert_info)
            else:
                self._handle_resolved_alert(comp, incident, alert_name)

    def _handle_firing_alert(self, comp, incident: Incident, alert_name: str, description: str, alert_info: AlertInfo):
        """
        Create a new incident on this component if none is running yet, or
        stack this alert onto the one already running.
        """
        if incident is None:
            # No running incident on this component yet: create one.
            incident = Incident(id=None, component_id=comp.id, title=alert_info.get_title())
            incident.add_entry(alert_name, description, comp.status, alert_info.notify)

            payload = {
                "incident": {
                    "name": incident.title,
                    "status": "investigating",
                    "body": incident.get_body(),
                    "impact_override": incident.get_impact(),
                    "deliver_notifications": alert_info.notify,
                    "component_ids": [comp.id],
                    "components": incident.get_components_payload(),
                }
            }

            response = self.statuspage_client.create_incident(payload)
            if response.status_code not in [200, 201]:
                logger.error(f"Error sending to Statuspage: {response.text}")
                raise RuntimeError("Failed to update Statuspage")

            incident_id = response.json().get("id")
            if not incident_id:
                logger.error(f"Statuspage response did not contain an incident ID for alert {alert_name} on component {comp.id}. Response was: {response.text}")
                return

            incident.id = incident_id
            self.incident_registry.register(incident)
            self.persist_incidents()
            logger.info(f"[SUCCESS] Created incident {incident.id} ({incident.status.value}) on component {comp.id} from alert {alert_name}.")
        else:
            # An incident is already running on this component: stack this
            # alert onto it (new bullet point, possible escalation to major_outage).
            incident.add_entry(alert_name, description, comp.status, alert_info.notify)

            payload = {
                "incident": {
                    "status": "investigating",
                    "body": incident.get_body(),
                    "impact_override": incident.get_impact(),
                    "deliver_notifications": alert_info.notify,
                    "components": incident.get_components_payload(),
                }
            }

            response = self.statuspage_client.update_incident(incident.id, payload)
            if response.status_code not in [200, 201]:
                logger.error(f"Error updating Statuspage incident {incident.id}: {response.text}")
                raise RuntimeError("Failed to update Statuspage")

            self.persist_incidents()
            logger.info(f"[SUCCESS] Stacked alert {alert_name} onto incident {incident.id} (now {incident.status.value}, {len(incident.entries)} active alert(s)).")

    def _handle_resolved_alert(self, comp, incident: Incident, alert_name: str):
        """
        Resolve this alert on the incident already running on this
        component, if any.
        """
        if incident is None or not self.incident_registry.is_running(incident):
            logger.warning(f"Could not find a running incident on component {comp.id} to update for resolved alert {alert_name}. Skipping.")
            return

        if not self.resolve_alert_entry(incident, alert_name):
            raise RuntimeError("Failed to update Statuspage")

    def resolve_alert_entry(self, incident: Incident, alert_name: str) -> bool:
        """
        Detach a resolved alert from the given incident and reflect the change on
        Statuspage: closes the incident if this was its last active alert,
        otherwise just drops the corresponding bullet point and keeps the
        incident open.

        Shared between the webhook handler (Alertmanager reports a "resolved"
        alert) and the periodic Alertmanager reconciliation (an alert is no
        longer active but its "resolved" webhook was never received).

        If the Statuspage API call fails, the alert is put back onto the incident
        so it is neither lost nor persisted in an inconsistent state: a later
        "resolved" webhook retry or the next reconciliation pass will attempt it
        again instead of silently forgetting about it.

        Returns True on success, False if the Statuspage API call failed.
        """
        removed_entry = incident.entries.get(alert_name)
        if removed_entry is None:
            return True

        incident.remove_entry(alert_name)

        if incident.is_empty():
            # last active alert on this component resolved: close the incident
            payload = {"incident": {"status": "resolved", "components": incident.get_components_payload(ComponentStatus.OPERATIONAL)}}

            response = self.statuspage_client.update_incident(incident.id, payload)
            if response.status_code not in [200, 201]:
                logger.error(f"Error resolving Statuspage incident {incident.id}: {response.text}")
                incident.entries[alert_name] = removed_entry
                return False

            self.incident_registry.resolve(incident)
            self.persist_incidents()
            logger.info(f"[SUCCESS] Successfully marked incident {incident.id} as resolved on Statuspage.")
        else:
            # other alerts are still active on this component: drop this
            # alert's bullet point but keep the incident open as-is
            payload = {
                "incident": {
                    "status": "investigating",
                    "body": incident.get_body(),
                    "impact_override": incident.get_impact(),
                    "components": incident.get_components_payload(),
                }
            }

            response = self.statuspage_client.update_incident(incident.id, payload)
            if response.status_code not in [200, 201]:
                logger.error(f"Error updating Statuspage incident {incident.id}: {response.text}")
                incident.entries[alert_name] = removed_entry
                return False

            self.persist_incidents()
            logger.info(f"[SUCCESS] Removed alert {alert_name} from incident {incident.id}; {len(incident.entries)} alert(s) still active.")

        return True

    def reconcile_with_alertmanager(self):
        """
        Compare the alerts backing each running Incident against what Alertmanager
        currently reports as active, and resolve (fully or partially) any
        Incident whose alert(s) are no longer firing.

        This covers alerts that resolved without the bridge ever receiving (or
        successfully processing) the corresponding "resolved" webhook: typically
        because the bridge was restarted, or a webhook delivery was lost.
        """
        logger.debug("Running Alertmanager reconciliation pass.")

        active_alertnames = self.alertmanager_client.get_active_alertnames()
        if active_alertnames is None:
            logger.warning("Skipping Alertmanager reconciliation: Alertmanager is unreachable.")
            return

        # Snapshot the list: resolving an incident's last entry mutates
        # the incident registry while we're iterating over it.
        resolved_count = 0
        for incident in list(self.incident_registry.running_incidents):
            stale_alert_names = [name for name in incident.entries if name not in active_alertnames]
            for alert_name in stale_alert_names:
                logger.info(f"Alert '{alert_name}' is no longer active on Alertmanager; resolving it on incident {incident.id}.")
                if self.resolve_alert_entry(incident, alert_name):
                    resolved_count += 1

        logger.debug(f"Alertmanager reconciliation pass complete: {resolved_count} alert(s) resolved.")
