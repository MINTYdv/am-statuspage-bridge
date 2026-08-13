import logging

import requests

logger = logging.getLogger("statuspage_bridge")


class AlertmanagerClient:
    """
    Thin wrapper around the Alertmanager API used by the bridge to check
    which alerts are still active, so resolved incidents can be caught even
    without a "resolved" webhook.
    """

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url
        self.timeout = timeout

    def get_active_alertnames(self) -> set[str] | None:
        """
        Query Alertmanager for the alerts it currently considers active (firing,
        not silenced, not inhibited), and return the set of their 'alertname'
        labels.

        Returns None if Alertmanager could not be reached or answered with an
        error, so callers can tell "no active alerts" apart from "we don't
        actually know" and skip reconciliation instead of wrongly resolving every
        running incident.
        """
        url = f"{self.base_url}/api/v2/alerts"
        params = {"active": "true", "silenced": "false", "inhibited": "false"}

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            logger.error(f"Could not reach Alertmanager at '{self.base_url}': {e}")
            return None

        if response.status_code != 200:
            logger.error(f"Error fetching active alerts from Alertmanager: {response.text}")
            return None

        active_alerts = response.json()
        return {
            alert["labels"]["alertname"] for alert in active_alerts if alert.get("status", {}).get("state") == "active" and "alertname" in alert.get("labels", {})
        }
