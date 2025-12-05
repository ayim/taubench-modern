import base64
import json
from typing import Any

from pydantic import BaseModel, Json, field_validator
from sema4ai.data import DataSource


class DocumentLayout(BaseModel):
    name: str
    data_model: str
    extraction_schema: Json[dict[str, Any]] | None = None
    translation_schema: Json[dict[str, Any]] | None = None
    summary: str | None = None
    extraction_config: Json[dict[str, Any]] | None = None
    system_prompt: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator(
        "extraction_schema",
        "translation_schema",
        "extraction_config",
        "system_prompt",
        mode="before",
    )
    @classmethod
    def validate_schema(cls, value: str | dict[str, Any] | None) -> str | None:
        # Accept a dict or a string which contains a json object
        if value is None:
            return None
        if isinstance(value, dict):
            import json

            return json.dumps(value)
        return value

    def insert(self, ds: DataSource) -> None:
        """Insert the DocumentLayout into the database."""
        # Encode JSONB fields as base64 for maximum SQL safety
        extraction_schema_val = (
            json.dumps(self.extraction_schema) if self.extraction_schema else "null"
        )
        b64_extraction_schema = base64.b64encode(extraction_schema_val.encode("utf-8")).decode(
            "utf-8"
        )

        translation_schema_val = (
            json.dumps(self.translation_schema) if self.translation_schema else "null"
        )
        b64_translation_schema = base64.b64encode(translation_schema_val.encode("utf-8")).decode(
            "utf-8"
        )

        extraction_config_val = (
            json.dumps(self.extraction_config) if self.extraction_config else "null"
        )
        b64_extraction_config = base64.b64encode(extraction_config_val.encode("utf-8")).decode(
            "utf-8"
        )

        params = {
            "name": self.name,
            "data_model": self.data_model,
            "b64_extraction_schema": b64_extraction_schema,
            "b64_translation_schema": b64_translation_schema,
            "b64_extraction_config": b64_extraction_config,
        }

        # Work around data library mishandling empty strings
        if self.summary:
            b64_summary = base64.b64encode(self.summary.encode("utf-8")).decode("utf-8")
            summary_fragment = "convert_from(decode($b64_summary, 'base64'), 'UTF8')::TEXT"
            params["b64_summary"] = b64_summary
        else:
            summary_fragment = "NULL"

        if self.system_prompt:
            b64_system_prompt = base64.b64encode(self.system_prompt.encode("utf-8")).decode("utf-8")
            system_prompt_fragment = (
                "convert_from(decode($b64_system_prompt, 'base64'), 'UTF8')::TEXT"
            )
            params["b64_system_prompt"] = b64_system_prompt
        else:
            system_prompt_fragment = "NULL"

        query = f"""
            INSERT INTO document_layouts
                (name, data_model, extraction_schema, translation_schema, summary,
                 extraction_config, system_prompt)
            VALUES
                ($name,
                 $data_model,
                 convert_from(decode($b64_extraction_schema, 'base64'), 'UTF8')::JSONB,
                 convert_from(decode($b64_translation_schema, 'base64'), 'UTF8')::JSONB,
                 {summary_fragment},
                 convert_from(decode($b64_extraction_config, 'base64'), 'UTF8')::JSONB,
                 {system_prompt_fragment}
                )
        """

        ds.native_query(
            query,
            params=params,
        )

    def update(self, ds: DataSource) -> None:
        """Update the schema in the database."""
        # Encode JSONB fields as base64 for maximum SQL safety
        extraction_schema_val = (
            json.dumps(self.extraction_schema) if self.extraction_schema else "null"
        )
        b64_extraction_schema = base64.b64encode(extraction_schema_val.encode("utf-8")).decode(
            "utf-8"
        )

        translation_schema_val = (
            json.dumps(self.translation_schema) if self.translation_schema else "null"
        )
        b64_translation_schema = base64.b64encode(translation_schema_val.encode("utf-8")).decode(
            "utf-8"
        )

        extraction_config_val = (
            json.dumps(self.extraction_config) if self.extraction_config else "null"
        )
        b64_extraction_config = base64.b64encode(extraction_config_val.encode("utf-8")).decode(
            "utf-8"
        )

        params = {
            "name": self.name,
            "data_model": self.data_model,
            "b64_extraction_schema": b64_extraction_schema,
            "b64_translation_schema": b64_translation_schema,
            "b64_extraction_config": b64_extraction_config,
        }

        # Work around data library mishandling empty strings
        if self.summary:
            b64_summary = base64.b64encode(self.summary.encode("utf-8")).decode("utf-8")
            summary_fragment = "convert_from(decode($b64_summary, 'base64'), 'UTF8')::TEXT"
            params["b64_summary"] = b64_summary
        else:
            summary_fragment = "NULL"

        if self.system_prompt:
            b64_system_prompt = base64.b64encode(self.system_prompt.encode("utf-8")).decode("utf-8")
            system_prompt_fragment = (
                "convert_from(decode($b64_system_prompt, 'base64'), 'UTF8')::TEXT"
            )
            params["b64_system_prompt"] = b64_system_prompt
        else:
            system_prompt_fragment = "NULL"

        query = f"""
            update document_layouts
            set
                extraction_schema = convert_from(decode($b64_extraction_schema, 'base64'),
                    'UTF8')::JSONB,
                translation_schema = convert_from(decode($b64_translation_schema, 'base64'),
                    'UTF8')::JSONB,
                summary = {summary_fragment},
                extraction_config = convert_from(decode($b64_extraction_config, 'base64'),
                    'UTF8')::JSONB,
                system_prompt = {system_prompt_fragment},
                updated_at = now()
            where name = $name and data_model = $data_model
        """

        ds.native_query(
            query,
            params=params,
        )

    def update_translation_schema(self, ds: DataSource, translation_schema: dict[str, Any]) -> None:
        """Update the translation schema in the database."""
        # Encode JSONB field as base64 for maximum SQL safety
        translation_schema_val = json.dumps(translation_schema)
        b64_translation_schema = base64.b64encode(translation_schema_val.encode("utf-8")).decode(
            "utf-8"
        )

        query = """
            update document_layouts
            set translation_schema = convert_from(decode($b64_translation_schema, 'base64'),
                'UTF8')::JSONB,
                updated_at = now()
            where name = $name and data_model = $data_model
        """
        ds.native_query(
            query,
            params={
                "name": self.name,
                "data_model": self.data_model,
                "b64_translation_schema": b64_translation_schema,
            },
        )

    def delete(self, ds: DataSource) -> bool:
        """Delete the schema from the database."""
        query = """
            delete from document_layouts
            where name = $name
            returning 1;
        """

        result = ds.native_query(
            query,
            params={
                "name": self.name,
            },
        )
        rows = [t for t in result.iter_as_tuples()]
        # expect one row which has one column
        if not rows or len(rows[0]) != 1:
            return False

        return rows[0][0] == 1

    @classmethod
    def find_all(cls, ds: DataSource) -> list["DocumentLayout"]:
        """Find all document layouts."""
        query = """
            select name, data_model, extraction_schema, translation_schema, summary,
                   extraction_config, system_prompt, created_at, updated_at from document_layouts
        """
        return ds.native_query(query).build_list(DocumentLayout)

    @classmethod
    def find_by_name(
        cls, ds: DataSource, data_model: str, layout_name: str
    ) -> "DocumentLayout | None":
        """Find a layout by name and data model."""
        query = """
            select name, data_model, extraction_schema, translation_schema, summary,
                   extraction_config, system_prompt, created_at, updated_at from document_layouts
            where data_model = $data_model and name = $layout_name
        """

        result = ds.native_query(
            query,
            params={
                "data_model": data_model,
                "layout_name": layout_name,
            },
        )
        dict_results = result.to_dict_list()
        if not dict_results:
            return None

        return DocumentLayout(**dict_results[0])  # type: ignore

    @classmethod
    def find_by_data_model(cls, ds: DataSource, data_model: str) -> list["DocumentLayout"]:
        """Find all layouts for a given data model."""
        query = """
            select name, data_model, extraction_schema, translation_schema, summary,
                   extraction_config, system_prompt, created_at, updated_at from document_layouts
            where data_model = $data_model
        """

        result = ds.native_query(
            query,
            params={
                "data_model": data_model,
            },
        )
        return result.build_list(DocumentLayout)

    @classmethod
    def delete_by_data_model(cls, ds: DataSource, data_model: str) -> int:
        """Bulk delete all layouts for a given data model.

        Args:
            ds: The data source connection
            data_model: The name of the data model

        Returns:
            int: Number of layouts deleted
        """
        query = """
            DELETE FROM document_layouts
            WHERE data_model = $data_model
            RETURNING name;
        """

        result = ds.native_query(
            query,
            params={
                "data_model": data_model,
            },
        )

        # Count the number of deleted layouts
        deleted_count = len([row for row in result.iter_as_tuples()])
        return deleted_count

    @classmethod
    def upsert_schema(
        cls,
        ds: DataSource,
        data_model_name: str,
        layout_name: str,
        extraction_schema: dict[str, Any],
        translation_schema: dict[str, Any],
        successful_config: dict[str, Any] | None = None,
    ) -> None:
        """Store schemas in the database with optional config information.

        Creates a new DocumentLayout if it doesn't exist, or updates existing one.
        This implements upsert behavior - insert if new, update if exists.

        Args:
            datasource: Document intelligence data source connection
            data_model_name: Data model name
            layout_name: Layout name
            extraction_schema: Extraction schema that worked
            translation_schema: Translation schema that worked
            successful_config: Optional config that led to success (for retry scenarios)
        """
        # Get the existing layout or create new one
        layout = DocumentLayout.find_by_name(ds, data_model_name, layout_name)

        if layout:
            # Update existing layout with successful schemas
            layout.extraction_schema = extraction_schema
            layout.translation_schema = translation_schema

            # If this was a retry success, store the config information
            if successful_config:
                layout.extraction_config = successful_config
                # Add metadata to indicate this was from retry
                summary_addition = " [Auto-updated from successful retry with config]"
                if layout.summary and summary_addition not in layout.summary:
                    layout.summary += summary_addition
                elif not layout.summary:
                    layout.summary = (
                        f"Layout updated with successful retry configuration{summary_addition}"
                    )

            layout.update(ds)
        else:
            # Layout doesn't exist, create new one
            summary = "Layout created from successful document processing"
            if successful_config:
                summary += " [Auto-created from successful retry with config]"

            layout = DocumentLayout(
                name=layout_name,
                data_model=data_model_name,
                extraction_schema=extraction_schema,
                translation_schema=translation_schema,
                summary=summary,
            )

            # If this was a retry success, store the config information
            if successful_config:
                layout.extraction_config = successful_config

            layout.insert(ds)
