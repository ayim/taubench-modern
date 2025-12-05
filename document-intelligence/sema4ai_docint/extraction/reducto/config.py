import copy
from typing import Any

# Reducto configuration
CUSTOM_CONFIG = {}


class ReductoConfig:
    """Simple class to provide Reducto configuration from embedded Python dict."""

    @classmethod
    def load_config(cls) -> dict[str, Any]:
        """Load the entire configuration."""
        return copy.deepcopy(CUSTOM_CONFIG)  # Return a deep copy to prevent modification
