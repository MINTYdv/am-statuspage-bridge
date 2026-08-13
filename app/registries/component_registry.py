import logging

from app.clients.statuspage_client import StatuspageClient
from app.models.statuspage_component import StatuspageComponent

logger = logging.getLogger("statuspage_bridge")


class ComponentRegistry:
    """
    Holds the Statuspage components and component groups loaded from the
    Statuspage API, and resolves alert component names (as used in the
    AlertManager alert labels) to their Statuspage component IDs.
    """

    def __init__(self):
        self.components: list[StatuspageComponent] = []
        self.components_groups: list[StatuspageComponent] = []

    def load(self, client: StatuspageClient, page_name: str) -> bool:
        """
        Method to load the components of the Statuspage page using the Statuspage API.
        This is useful to link the alerts to the correct components only using the component name in the AlertManager alert summary,
        and to avoid hardcoding the component IDs in the AlertManager alert summaries.

        Creates StatuspageComponent objects
        """

        response = client.get_component_groups()
        if response.status_code != 200:
            logger.error(f"Error fetching component groups from Statuspage: {response.text}")
            return False

        component_groups_data = response.json()
        if component_groups_data:
            for group in component_groups_data:
                group_id = group["id"]
                group_name = group["name"]
                logger.debug(f"Loading component group '{group_name}' (ID: {group_id}) from Statuspage...")

                self.components_groups.append(StatuspageComponent(group_id, group_name))
                logger.debug(f"Loaded component group '{group_name}' (ID: {group_id}) from Statuspage.")
            logger.info(f"[SUCCESS] Loaded {len(self.components_groups)} component group(s) from Statuspage page '{page_name}' (ID: {client.page_id}).")

        # Get components from Statuspage API
        response = client.get_components()
        if response.status_code != 200:
            logger.error(f"Error fetching components from Statuspage: {response.text}")
            return False

        components_data = response.json()
        loaded_amount = 0

        for comp in components_data:
            if comp.get("group"):
                continue  # the component is a group, it will be managed in the previous loop

            logger.debug(f"Loading component '{comp['name']}' (ID: {comp['id']}) from Statuspage...")
            if comp.get("group_id"):
                parent_group = self.get_group_by_id(comp["group_id"])
                if not parent_group:
                    logger.error(f"Parent group with ID '{comp['group_id']}' not found for component '{comp['name']}' (ID: {comp['id']}). Skipping this component.")
                    continue
                new_comp = StatuspageComponent(comp["id"], comp["name"])
                parent_group.children.append(new_comp)
                logger.debug(f"Loaded component '{comp['name']}' (ID: {comp['id']}) under group '{parent_group.name}' from Statuspage.")
            else:
                self.components.append(StatuspageComponent(comp["id"], comp["name"]))
                logger.debug(f"Loaded component '{comp['name']}' (ID: {comp['id']}) without group from Statuspage.")
            loaded_amount += 1

        logger.info(f"[SUCCESS] Loaded {loaded_amount} component(s) from Statuspage page '{page_name}' (ID: {client.page_id}).")
        return True

    def get_by_id(self, id: str) -> StatuspageComponent:
        """
        Gets a Statuspage component by its ID.

        Arguments:
            id (str): the Statuspage API ID of the statuspagecomponent

        Returns:
            a StatuspageComponent object corresponding to the provided ID, or None if none could be found.
        """

        for c in self.components + self.components_groups:
            if c.id == id:
                return c
        return None

    def get_id_by_name(self, name: str) -> str:
        """
        Method to get the component ID from the component name.
        This is useful to avoid hardcoding the component IDs in the AlertManager alert summaries.
        It uses the components cache loaded at startup to find the correct component ID based on the component name provided in the AlertManager alert summary.
        """

        splitted = name.split("/")
        if len(splitted) == 2:
            group_name, comp_name = splitted[0].strip(), splitted[1].strip()
            for group in self.components_groups:
                if group.name.lower() == group_name.lower():
                    for comp in group.children:
                        if comp.name.lower() == comp_name.lower():
                            return comp.id
            logger.error(f"Component with name '{comp_name}' not found in Statuspage components groups for group '{group_name}'.")
            return None
        else:
            for comp in self.components:
                if comp.name.lower() == name.lower():
                    return comp.id
            logger.error(f"Component with name '{name}' not found in Statuspage components.")
        return None

    def get_group_by_id(self, id: str) -> StatuspageComponent:
        """
        Method to get the component group from the component group ID.
        This is useful to find the correct component group based on the component group ID provided in the Statuspage component response
        It uses the components groups cache loaded at startup to find the correct component group based on the component group ID provided
        """
        for group in self.components_groups:
            if group.id == id:
                return group
        logger.error(f"Component group with ID '{id}' not found in Statuspage component groups.")
        return None
