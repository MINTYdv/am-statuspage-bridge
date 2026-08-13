class ConfigHelper:
    """
    Utils methods to parse information from diverse objects.
    """

    def __init__(self):
        pass

    @staticmethod
    def parse_bool(value: str) -> bool:
        """
        Parses a string into a boolean.
        Raises a ValueError if the string does not match any expected format.
        """
        normalized_value = str(value).strip().lower()

        truth_values = {"true", "yes", "on", "1"}
        false_values = {"false", "no", "off", "0"}

        if normalized_value in truth_values:
            return True
        if normalized_value in false_values:
            return False

        raise ValueError(f"Cannot convert '{value}' to a valid boolean.")
