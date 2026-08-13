import requests


class StatuspageClient:
    """
    Thin wrapper around the Statuspage API endpoints used by the bridge.
    Only handles HTTP transport and authentication: turning the raw
    responses into domain objects (components, incidents) is someone else's
    job, so this class stays a drop-in piece on its own.
    """

    def __init__(self, api_key: str, page_id: str):
        self.api_key = api_key
        self.page_id = page_id
        self.base_url = f"https://api.statuspage.io/v1/pages/{page_id}"
        self.incidents_url = f"{self.base_url}/incidents"

    @property
    def headers(self) -> dict:
        return {"Authorization": f"OAuth {self.api_key}", "Content-Type": "application/json"}

    def get_page(self) -> requests.Response:
        """
        Method to fetch the Statuspage page details. Used to validate the
        API key / page ID pair and to retrieve the page's public name.
        """
        return requests.get(self.base_url, headers=self.headers)

    def get_component_groups(self) -> requests.Response:
        """
        Method to fetch the raw component groups from the Statuspage API.
        """
        return requests.get(f"{self.base_url}/component-groups", headers=self.headers)

    def get_components(self) -> requests.Response:
        """
        Method to fetch the raw components from the Statuspage API.
        """
        return requests.get(f"{self.base_url}/components", headers=self.headers)

    def create_incident(self, payload: dict) -> requests.Response:
        """
        Method to create a new incident on Statuspage.

        Arguments:
            payload (dict): the JSON body expected by the Statuspage incidents endpoint
        """
        return requests.post(self.incidents_url, json=payload, headers=self.headers)

    def update_incident(self, incident_id: str, payload: dict) -> requests.Response:
        """
        Method to update (or resolve, depending on the payload's status) an
        existing incident on Statuspage.

        Arguments:
            incident_id (str): the Statuspage incident ID to update
            payload (dict): the JSON body expected by the Statuspage incidents endpoint
        """
        return requests.patch(f"{self.incidents_url}/{incident_id}", json=payload, headers=self.headers)
