NOT_CONFIGURED = "SEMA4AI_FIELD_NOT_CONFIGURED"
"""Value to be used when a field is not configured in the configuration file."""

AZURE_URL_PATTERN = r"^(https?://[^/]+)/openai/deployments/([^/]+)/(chat/completions|embeddings)\?api-version=(.+)$"
"""Pattern to match an Azure URL for the OpenAI API."""

RAW_CONTEXT = {"raw": True}
"""Serialization context to be used with the `raw` key set to True to indicate
that the value should be serialized in its raw form.
"""

DEFAULT_ARCHITECTURE = "agent_architecture_default"
"""Base agent architecture name."""

LEGACY_ARCH_CONTEXT = {"serialize_legacy_names": True}
"""Serialization context to be used with the `serialize_legacy_names` key set to True to indicate
that the value should be serialized in its legacy form.
"""
