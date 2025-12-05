import base64
import json
from typing import Any

from pydantic import BaseModel, Json, field_validator
from sema4ai.data import DataSource


class DataModel(BaseModel):
    name: str
    description: str
    model_schema: Json[dict[str, Any]]
    views: Json[list[dict[str, Any]]] | None = None
    quality_checks: Json[list[dict[str, str]]] | None = None
    prompt: str | None = None
    base_config: Json[dict[str, Any]] | None = None
    summary: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator("model_schema", "views", "quality_checks", "base_config", mode="before")
    @classmethod
    def validate_json_fields(cls, value: dict[str, Any] | list[Any] | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, dict | list):
            return json.dumps(value)
        return value

    def insert(self, ds: DataSource) -> None:
        """Insert the data model into the database."""

        # Encode fields as base64 for maximum SQL safety
        b64_description = base64.b64encode(self.description.encode("utf-8")).decode("utf-8")

        model_schema_val = json.dumps(self.model_schema)
        b64_model_schema = base64.b64encode(model_schema_val.encode("utf-8")).decode("utf-8")

        views_val = json.dumps(self.views) if self.views else "[]"
        b64_views = base64.b64encode(views_val.encode("utf-8")).decode("utf-8")

        quality_checks_val = json.dumps(self.quality_checks) if self.quality_checks else "[]"
        b64_quality_checks = base64.b64encode(quality_checks_val.encode("utf-8")).decode("utf-8")

        params = {
            "name": self.name,
            "b64_description": b64_description,
            "b64_model_schema": b64_model_schema,
            "b64_views": b64_views,
            "b64_quality_checks": b64_quality_checks,
        }

        # Work around data library mishandling empty strings
        if self.summary:
            b64_summary = base64.b64encode(self.summary.encode("utf-8")).decode("utf-8")
            summary_fragment = "convert_from(decode($b64_summary, 'base64'), 'UTF8')::TEXT"
            params["b64_summary"] = b64_summary
        else:
            summary_fragment = "NULL"

        # Set prompt as NULL if prompt parameter is None or empty string
        prompt_fragment = "NULL"
        if self.prompt:
            b64_prompt = base64.b64encode(self.prompt.encode("utf-8")).decode("utf-8")
            prompt_fragment = "convert_from(decode($b64_prompt, 'base64'), 'UTF8')::TEXT"
            params["b64_prompt"] = b64_prompt

        # Set base_config as NULL if base_config parameter is None or empty string
        base_config_fragment = "NULL"
        if self.base_config:
            base_config_val = json.dumps(self.base_config)
            b64_base_config = base64.b64encode(base_config_val.encode("utf-8")).decode("utf-8")
            base_config_fragment = "convert_from(decode($b64_base_config, 'base64'), 'UTF8')::JSONB"
            params["b64_base_config"] = b64_base_config

        query = f"""
            INSERT INTO data_models
                (name, description, model_schema, views, quality_checks, prompt, summary,
                 base_config)
            VALUES
                ($name,
                 convert_from(decode($b64_description, 'base64'), 'UTF8')::TEXT,
                 convert_from(decode($b64_model_schema, 'base64'), 'UTF8')::JSONB,
                 convert_from(decode($b64_views, 'base64'), 'UTF8')::JSONB,
                 convert_from(decode($b64_quality_checks, 'base64'), 'UTF8')::JSONB,
                 {prompt_fragment},
                 {summary_fragment},
                 {base_config_fragment}
                )
        """

        ds.native_query(query, params=params)

    def update(self, ds: DataSource) -> None:
        """Update the data model in the database."""

        # Encode fields as base64 for maximum SQL safety
        b64_description = base64.b64encode(self.description.encode("utf-8")).decode("utf-8")

        model_schema_val = json.dumps(self.model_schema)
        b64_model_schema = base64.b64encode(model_schema_val.encode("utf-8")).decode("utf-8")

        views_val = json.dumps(self.views) if self.views else "[]"
        b64_views = base64.b64encode(views_val.encode("utf-8")).decode("utf-8")

        quality_checks_val = json.dumps(self.quality_checks) if self.quality_checks else "[]"
        b64_quality_checks = base64.b64encode(quality_checks_val.encode("utf-8")).decode("utf-8")

        params = {
            "name": self.name,
            "b64_description": b64_description,
            "b64_model_schema": b64_model_schema,
            "b64_views": b64_views,
            "b64_quality_checks": b64_quality_checks,
        }

        # Work around data library mishandling empty strings
        if self.summary:
            b64_summary = base64.b64encode(self.summary.encode("utf-8")).decode("utf-8")
            summary_fragment = "convert_from(decode($b64_summary, 'base64'), 'UTF8')::TEXT"
            params["b64_summary"] = b64_summary
        else:
            summary_fragment = "NULL"

        # Set prompt as NULL if prompt parameter is None or empty string
        prompt_fragment = "NULL"
        if self.prompt:
            b64_prompt = base64.b64encode(self.prompt.encode("utf-8")).decode("utf-8")
            prompt_fragment = "convert_from(decode($b64_prompt, 'base64'), 'UTF8')::TEXT"
            params["b64_prompt"] = b64_prompt

        # Set base_config as NULL if base_config parameter is None or empty string
        base_config_fragment = "NULL"
        if self.base_config:
            base_config_val = json.dumps(self.base_config)
            b64_base_config = base64.b64encode(base_config_val.encode("utf-8")).decode("utf-8")
            base_config_fragment = "convert_from(decode($b64_base_config, 'base64'), 'UTF8')::JSONB"
            params["b64_base_config"] = b64_base_config

        query = f"""
            update data_models
            set
                description = convert_from(decode($b64_description, 'base64'), 'UTF8')::TEXT,
                model_schema = convert_from(decode($b64_model_schema, 'base64'), 'UTF8')::JSONB,
                views = convert_from(decode($b64_views, 'base64'), 'UTF8')::JSONB,
                quality_checks = convert_from(decode($b64_quality_checks, 'base64'), 'UTF8')::JSONB,
                summary = {summary_fragment},
                prompt = {prompt_fragment},
                base_config = {base_config_fragment},
                updated_at = now()
            where name = $name
        """

        ds.native_query(
            query,
            params=params,
        )

    def set_prompt(self, ds: DataSource, prompt: str | None) -> None:
        """Set the data model prompt."""

        params = {
            "name": self.name,
        }

        # Set prompt as NULL if prompt parameter is None or empty string
        prompt_fragment = "NULL"
        if prompt:
            b64_prompt = base64.b64encode(prompt.encode("utf-8")).decode("utf-8")
            prompt_fragment = "convert_from(decode($b64_prompt, 'base64'), 'UTF8')::TEXT"
            params["b64_prompt"] = b64_prompt

        query = f"""
            update data_models
            set
                prompt = {prompt_fragment},
                updated_at = now()
            where name = $name
        """
        ds.native_query(query, params=params)

    def set_base_config(self, ds: DataSource, base_config: dict[str, Any] | None) -> None:
        """Set the data model base_config."""

        params = {
            "name": self.name,
        }

        # Set base_config as NULL if base_config parameter is None or empty string
        base_config_fragment = "NULL"
        if base_config:
            base_config_val = json.dumps(base_config)
            b64_base_config = base64.b64encode(base_config_val.encode("utf-8")).decode("utf-8")
            base_config_fragment = "convert_from(decode($b64_base_config, 'base64'), 'UTF8')::JSONB"
            params["b64_base_config"] = b64_base_config

        query = f"""
            update data_models
            set
                base_config = {base_config_fragment},
                updated_at = now()
            where name = $name
        """
        ds.native_query(query, params=params)

    def delete(self, ds: DataSource) -> bool:
        """Delete the data model from the database and drop associated views."""
        from sema4ai_docint.logging import logger

        # First, drop all views associated with this data model
        if self.views:
            from sema4ai_docint.models.constants import PROJECT_NAME
            from sema4ai_docint.views import ViewGenerator

            # Create view generator to properly drop views
            view_generator = ViewGenerator(project_name=PROJECT_NAME)

            for view in self.views:
                view_name = view.get("name")
                if view_name:
                    logger.info(f"Attempting to drop view: {view_name}")
                    try:
                        # Try dropping as MindsDB view
                        view_generator.drop_mindsdb_view(view_name)
                    except Exception as e:
                        logger.debug(f"Failed to drop MindsDB view {view_name}: {e}")
                    try:
                        # Also try dropping as Postgres-native view
                        ViewGenerator.drop_postgres_view(view_name, ds)
                    except Exception as e:
                        logger.debug(f"Failed to drop Postgres view {view_name}: {e}")

        # Then delete the data model record from the database
        query = """
            delete from data_models
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
    def find_all(cls, ds: DataSource) -> list["DataModel"]:
        """Find all data models."""
        query = """
            select name, description, model_schema, views, quality_checks, prompt, summary,
                   base_config, created_at, updated_at from data_models
        """
        return ds.native_query(query).build_list(DataModel)

    @classmethod
    def find_by_name(cls, ds: DataSource, name: str) -> "DataModel | None":
        """Find a data model by name."""
        query = """
            select name, description, model_schema, views, quality_checks, prompt, summary,
                   base_config, created_at, updated_at from data_models
            where name = $name
        """

        result = ds.native_query(
            query,
            params={
                "name": name,
            },
        )
        dict_results = result.to_dict_list()
        if not dict_results:
            return None

        return DataModel(**dict_results[0])  # type: ignore

    def to_json(self) -> dict[str, Any]:
        """Return a JSON representation of the data model"""
        return self.model_dump(
            exclude={
                "created_at": True,
                "updated_at": True,
                "views": {"__all__": {"sql"}},
            }
        )
