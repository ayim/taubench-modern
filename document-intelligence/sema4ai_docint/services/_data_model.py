"""
Layout service for document layout operations.
"""

import json
from dataclasses import asdict
from typing import Any, Literal

from sema4ai_docint.logging import logger
from sema4ai_docint.models.constants import (
    DATA_SOURCE_NAME,
    DEFAULT_LAYOUT_NAME,
    PROJECT_NAME,
)
from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.models.document_layout import DocumentLayout
from sema4ai_docint.models.initialize import initialize_dataserver
from sema4ai_docint.services.exceptions import DataModelServiceError
from sema4ai_docint.utils import _filter_jsonschema, _replace_jsonschema_values, normalize_name
from sema4ai_docint.views.views import View, ViewGenerator, transform_business_schema

from ._context import _DIContext

LAYOUT_DESCRIPTION_KEY = "layout_description"


class _DataModelService:
    def __init__(self, context: _DIContext) -> None:
        self._context = context

    def generate_from_file(self, file_name: str, user_prompt: str | None = None) -> dict[str, Any]:
        """Generate a data model schema from an uploaded document file.

        Args:
            file_name: The name of the file to generate a data model from
            user_prompt: Additional instructions for the schema generation process

        Returns:
            Response with generated schema and success message

        Raises:
            DataModelServiceError: If schema generation fails
        """

        try:
            schema = self._context.agent_client.generate_schema(file_name, user_prompt)
        except Exception as e:
            raise DataModelServiceError(f"Failed to generate data model schema: {e}") from e

        return {"message": "Data model generated successfully", "schema": schema}

    def modify_schema(
        self, schema: dict[str, Any], instructions: str, file_name: str | None = None
    ) -> dict[str, Any]:
        """Modify a data model schema based on provided instructions.

        Args:
            schema: The schema to modify
            instructions: The instructions to modify the schema
            file_name: The file name to use to modify the schema

        Returns:
            Response with modified schema and success message

        Raises:
            DataModelServiceError: If schema modification fails
        """
        try:
            schema = self._context.agent_client.modify_schema(schema, instructions, file_name)
        except Exception as e:
            raise DataModelServiceError(f"Failed to modify data model schema: {e}") from e

        return {"message": "Data model schema modified successfully", "schema": schema}

    def create_from_schema(
        self,
        name: str,
        description: str,
        json_schema_text: str,
        prompt: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        """Create a new data model from JSON schema. Creates business views and default layout.

        Args:
            datasource: The document intelligence data source connection
            name: The name of the data model
            description: The description of the data model
            json_schema_text: The JSON schema to use to create the data model
            prompt: The prompt for the data model
            summary: (optional) The summary of the data model

        Returns:
            Response The data model

        Raises:
            DataModelServiceError: If data model already exists or creation fails
        """
        json_schema = self._context.agent_client.sanitize_json_schema(json.loads(json_schema_text))

        # Filter the singular schema into a data model schema and a document layout schema
        data_model_schema, document_layout_schema = self._filter_schemas(json_schema)

        original_name = name
        name = normalize_name(name)

        # Check if data model with this name already exists
        existing_model = DataModel.find_by_name(self._context.datasource, name)
        if existing_model:
            raise DataModelServiceError(
                f"Cannot create data model '{original_name}' because after normalizing "
                f"special characters it becomes '{name}', which already exists in the system."
            )

        data_model = DataModel(
            name=name,
            description=description,
            model_schema=data_model_schema,
            prompt=prompt,
            summary=summary,
        )

        # Generate a summary for the data model if it doesn't have one
        if not data_model.summary:
            summary = self._context.agent_client.summarize_with_args(
                {
                    "Data model name": name,
                    "Data model description": description,
                    "Data model schema": data_model_schema,
                }
            )
            data_model.summary = summary

        data_model.insert(self._context.datasource)

        # Create views
        try:
            self.create_business_views(name)
        except Exception as e:
            logger.error(f"Error creating views for data model {name}: {e!s}")
            # clean up the data model
            data_model.delete(self._context.datasource)
            raise DataModelServiceError(
                f"Failed to create views for data model {name}: {e!s}"
            ) from e

        # Create default layout using the business schema
        self._create_or_update_default_layout(name, data_model_schema, document_layout_schema)

        # Fetch the final data_model
        new_data_model = data_model.find_by_name(self._context.datasource, name)
        if not new_data_model:
            raise DataModelServiceError(f"Failed to create data model: {name}")

        return new_data_model.to_json()

    def create_business_views(self, data_model_name: str, force: bool = False) -> dict[str, str]:
        """Create SQL views for a data model in the database.

        Args:
            datasource: The document intelligence data source connection
            data_model_name: The name of the data model

        Returns:
            Response with success message

        Raises:
            DataModelServiceError: If data model not found, project creation fails, or
                view generation fails
        """
        data_model_name = normalize_name(data_model_name)
        data_model = DataModel.find_by_name(self._context.datasource, data_model_name)
        if not data_model:
            raise DataModelServiceError(f"Data model with name {data_model_name} not found")

        # Generate MindsDB views (existing logic)
        mindsdb_views = self._generate_views(data_model, view_type="mindsdb")
        mindsdb_views_dict = [asdict(v) for v in mindsdb_views]

        # Create MindsDB views (existing)
        initialize_dataserver(PROJECT_NAME, mindsdb_views_dict, force=force)

        # Create Postgres views directly in database
        postgres_views = self._generate_views(data_model, view_type="postgres")
        ViewGenerator.create_postgres_views(postgres_views, self._context.datasource)

        data_model.views = mindsdb_views_dict
        data_model.update(self._context.datasource)

        return {"Message": "Business views created successfully"}

    def _generate_views(
        self, data_model: DataModel, view_type: Literal["mindsdb", "postgres"] = "mindsdb"
    ) -> list[View]:
        """Generate views for a data model.

        Args:
            data_model: The data model to generate views for
            view_type: The type of views to generate - "mindsdb" or "postgres"

        Returns:
            A list of View objects

        Raises:
            DataModelServiceError: If view generation fails
        """
        try:
            # Transform JSON Schema to BusinessSchema format
            business_schema = transform_business_schema(data_model.model_schema)

            # Configure generator based on view type
            if view_type == "mindsdb":
                datasource_name = DATA_SOURCE_NAME
                project_name = PROJECT_NAME
            else:  # postgres
                datasource_name = None
                project_name = None

            # Generate views
            generator = ViewGenerator(
                source_table_name="documents",
                document_column_name="translated_content",
                datasource_name=datasource_name,
                project_name=project_name,
            )

            return generator.generate_views(business_schema, data_model.name)
        except Exception as e:
            logger.error(f"Error generating {view_type} views: {e!s}")
            raise DataModelServiceError(f"Error generating {view_type} views: {e!s}") from e

    def _create_or_update_default_layout(
        self,
        data_model_name: str,
        data_model_schema: dict[str, Any],
        document_layout_schema: dict[str, Any],
    ) -> None:
        """Create or update the default layout for a data model.

        This method handles the creation or update of the default layout for a data model.
        The business schema is used directly as the extraction schema, and a direct mapping
        is created for the translation schema.

        Args:
            datasource: The document intelligence data source connection
            data_model_name: The name of the data model
            business_schema: The business schema to base the layout on
        """
        existing_layout = None
        data_model_name = normalize_name(data_model_name)
        existing_layout = DocumentLayout.find_by_name(
            self._context.datasource, data_model_name, DEFAULT_LAYOUT_NAME
        )

        mapping_rules = []
        for field_name in data_model_schema.get("properties", {}).keys():
            mapping_rules.append(
                {
                    "source": field_name,
                    "target": field_name,
                }
            )

        translation_schema = {"rules": mapping_rules}

        # Generate summary for the default layout or if existing layout has no summary
        summary = None
        if not existing_layout or not existing_layout.summary:
            summary = self._context.agent_client.summarize_with_args(
                {
                    "Layout name": DEFAULT_LAYOUT_NAME,
                    "Data model name": data_model_name,
                    "Layout schema": document_layout_schema,
                }
            )

        if existing_layout:
            existing_layout.extraction_schema = document_layout_schema
            existing_layout.translation_schema = translation_schema
            existing_layout.summary = summary
            existing_layout.update(self._context.datasource)
        else:
            layout = DocumentLayout(
                name=DEFAULT_LAYOUT_NAME,
                data_model=data_model_name,
                extraction_schema=document_layout_schema,
                translation_schema=translation_schema,
                summary=summary,
            )
            layout.insert(self._context.datasource)

    def _filter_schemas(self, schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Filter the given schema into a data model schema and a document layout schema.

        Args:
            schema: The schema to filter

        Returns:
            The filtered schema
        """
        # The data-model schema is exactly as the user provided but with any `layout_description`
        # keys removed
        data_model_schema = _filter_jsonschema(schema, lambda key: key == LAYOUT_DESCRIPTION_KEY)

        # The document layout schema is the same as the data-model schema but the layout_description
        # keys replace the description keys, and then the layout_description keys are removed.
        document_layout_schema = _replace_jsonschema_values(
            schema, {"description": LAYOUT_DESCRIPTION_KEY}
        )
        document_layout_schema = _filter_jsonschema(
            document_layout_schema, lambda key: key == LAYOUT_DESCRIPTION_KEY
        )

        return data_model_schema, document_layout_schema
