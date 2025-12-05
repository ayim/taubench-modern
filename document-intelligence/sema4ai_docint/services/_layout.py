"""
Layout service for document layout operations.
"""

import json

from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.models.mapping import Mapping, MappingRow
from sema4ai_docint.services.exceptions import LayoutServiceError
from sema4ai_docint.utils import normalize_name

from ._context import _DIContext


class _LayoutService:
    def __init__(self, context: _DIContext) -> None:
        self._context = context

    def generate_translation_schema(
        self,
        data_model_name: str,
        layout_schema: str,
    ) -> dict:
        """
        Create translation rules to map layout schema to data model schema.

        Args:
            data_model_name: The name of the data model to generate a translation schema for
            layout_schema: Extraction schema of the layout to generate a translation schema for

        Returns:
            Dict containing translation mapping rules

        Raises:
            LayoutServiceError: If mapping generation fails
        """
        try:
            data_model_name = normalize_name(data_model_name)

            data_model = DataModel.find_by_name(self._context.datasource, data_model_name)
            if not data_model:
                raise ValueError(f"Data model with name {data_model_name} not found")

            # Convert model_schema to string if it's a dict
            model_schema_str = data_model.model_schema
            if isinstance(model_schema_str, dict):
                model_schema_str = json.dumps(model_schema_str)

            return self._generate_translation_schema(model_schema_str, layout_schema)
        except Exception as e:
            raise LayoutServiceError(f"Failed to generate translation schema: {e}") from e

    def _generate_translation_schema(self, data_model_schema: str, layout_schema: str) -> dict:
        """
        Create a set of rules to translate JSON objects from the layout's schema to the data
        model's schema.

        Args:
            data_model_schema: The data model's schema
            layout_schema: The layout's schema

        Returns:
            The translation schema
        """
        client = self._context.agent_client

        mapping_rules_text = client.create_mapping(data_model_schema, layout_schema)
        mapping_rules = json.loads(mapping_rules_text)

        if not isinstance(mapping_rules, list):
            raise ValueError("mapping should be a list")

        mapping = Mapping(rules=[MappingRow(**rule) for rule in mapping_rules])
        return mapping.model_dump()
