class StatuspageComponent:
    """
    Represents a component in Statuspage.
    Those components are loaded from the Statuspage API and are used to link incidents to components
    Each component has an ID and a name.
    """

    def __init__(self, id: str, name: str, children: list["StatuspageComponent"] = None):
        self.id = id
        self.name = name
        self.children = children if children is not None else []

    def is_group(self):
        """Returns True if the component is a group (i.e. has child components), False otherwise."""
        return len(self.children) > 0
