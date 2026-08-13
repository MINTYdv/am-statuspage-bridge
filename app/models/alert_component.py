from enum import Enum


class ComponentStatus(str, Enum):
    MAJOR_OUTAGE = "major_outage"
    PARTIAL_OUTAGE = "partial_outage"
    OPERATIONAL = "operational"
    DEGRADED_PERFORMANCE = "degraded_performance"
    UNDER_MAINTENANCE = "under_maintenance"
    NO_UPDATE = ""


class AlertComponent:
    def __init__(self, id: str, status: ComponentStatus):
        self.id = id
        self.status = status
