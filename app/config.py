import os
from dataclasses import dataclass


@dataclass
class BridgeConfig:
    """
    Holds every environment-driven setting the bridge needs.
    Centralizing them here means the bridge itself never touches os.getenv
    directly, which is what makes it possible to instantiate (and test) it
    as a plain library object instead of a script tied to its own process
    environment.
    """

    statuspage_api_key: str
    statuspage_page_id: str
    secret_webhook: str
    alertmanager_url: str
    incidents_store_path: str
    alertmanager_poll_interval_seconds: int
    log_level: str

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        """
        Method to build a BridgeConfig by reading it from the process
        environment variables, falling back to sane defaults where possible.
        """
        return cls(
            statuspage_api_key=os.getenv("STATUSPAGE_API_KEY"),
            statuspage_page_id=os.getenv("STATUSPAGE_PAGE_ID"),
            secret_webhook=os.getenv("SECRET_WEBHOOK"),
            alertmanager_url=os.getenv("ALERTMANAGER_URL", "http://alertmanager:9093"),
            incidents_store_path=os.getenv("INCIDENTS_STORE_PATH", "/app/data/incidents_store.json"),
            alertmanager_poll_interval_seconds=int(os.getenv("ALERTMANAGER_POLL_INTERVAL_SECONDS", "60")),
            # DEBUG is handy locally but far too verbose for production (dumps
            # one line per outgoing HTTP request); INFO is the sane default.
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def missing_required_vars(self) -> list[str]:
        """
        Method to list the required settings that are missing, so the bridge
        can warn loudly at startup instead of failing later with a cryptic
        Statuspage 401.
        """
        required = {"STATUSPAGE_API_KEY": self.statuspage_api_key, "STATUSPAGE_PAGE_ID": self.statuspage_page_id, "SECRET_WEBHOOK": self.secret_webhook}
        return [name for name, value in required.items() if not value]
