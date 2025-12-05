from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sema4ai.actions import Table

from sema4ai_docint.extraction.process import (
    ExtractAndTransformContentParams,
    ExtractionSchema,
    TranslationSchema,
    validate_and_parse_schemas,
)
from sema4ai_docint.extraction.reducto.config import ReductoConfig
from sema4ai_docint.extraction.transform import TransformDocumentLayout, transform_content
from sema4ai_docint.logging import logger
from sema4ai_docint.utils import compute_document_id, normalize_name
from sema4ai_docint.validation.models import ValidationRule, ValidationSummary
from sema4ai_docint.validation.validate import validate_document_extraction

from ..models import DataModel, Document, DocumentLayout, initialize_dataserver
from ..models.constants import DEFAULT_LAYOUT_NAME, PROJECT_NAME
from ._context import _DIContext
from .exceptions import DocumentServiceError


@dataclass
class _Experiment:
    """Represents a single processing experiment configuration.

    Attributes:
        name: Human-readable name for the experiment
        extraction_config: Optional Reducto extraction configuration
        user_prompt: Optional user prompt for processing
        layout_prompt: Optional layout prompt for processing
    """

    name: str
    extraction_config: dict[str, Any] | None = None
    user_prompt: str | None = None
    layout_prompt: str | None = None


class _ExperimentResult(BaseModel):
    """Result of running a single experiment.

    Attributes:
        experiment_name: Name of the experiment that was run
        success: Whether the experiment succeeded
        error_message: Error message if experiment failed (None if successful)
        validation_results: Validation results if experiment succeeded
    """

    document: Document | None = None
    experiment_name: str
    success: bool
    error_message: str | None = None
    validation_results: ValidationSummary | None = None


class _ProcessingResponse(BaseModel):
    """Response from document processing with experiments.

    Attributes:
        success: Overall success status
        document: Processed document data
        experiments: List of experiment results showing what was tried
        successful_experiment: Name of the experiment that succeeded (None if all failed)
        total_attempts: Total number of experiments attempted
    """

    success: bool
    document: Document | None = None
    experiments: list[_ExperimentResult]
    successful_experiment: str | None = None
    total_attempts: int


class _DocumentService:
    def __init__(self, context: _DIContext) -> None:
        self._context = context

    def document_id(self, file_name: str) -> str:
        """
        Localizes and computes the document ID for a given file name.

        """
        from sema4ai_docint.utils import compute_document_id

        if self._context.agent_server_transport is None:
            raise DocumentServiceError("AgentServer not configured")

        file_path = self._context.agent_server_transport.get_file(file_name)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        return compute_document_id(file_path)

    def query(self, document_id: str) -> dict[str, Table | None] | Table | None:
        """Get document in data model format.

        Args:
            document_id: Document ID to retrieve

        Returns:
            Dictionary mapping view names to their Table results when multiple views,
            or the single Table directly when only one view, or None if no views.

        Raises:
            DocumentServiceError: If document or data model not found
        """
        document = Document.find_by_id(self._context.datasource, document_id)
        if not document:
            raise DocumentServiceError(f"Document with ID {document_id} not found")

        data_model = DataModel.find_by_name(self._context.datasource, document.data_model)
        if not data_model:
            raise DocumentServiceError(f"Data model with name {document.data_model} not found")

        view_names = self._extract_view_names(data_model)

        try:
            initialize_dataserver(PROJECT_NAME, data_model.views)
        except Exception as e:
            raise DocumentServiceError(
                "Failed to create the document intelligence data-server project"
            ) from e

        results_dict = self._collect_view_results(view_names, document_id)

        return results_dict

    def _extract_view_names(self, data_model: DataModel) -> list[str]:
        """Extract view names from data model.

        Args:
            data_model: Data model to extract view names from

        Returns:
            List of view names

        Raises:
            DocumentServiceError: If no views found
        """
        view_names = []
        if data_model.views:
            for view in data_model.views:
                if isinstance(view, dict) and "name" in view:
                    view_names.append(view["name"])

        if not view_names:
            raise DocumentServiceError(f"No views found for data model {data_model.name}")

        return view_names

    def _collect_view_results(
        self, view_names: list[str], document_id: str
    ) -> dict[str, Table | None] | Table | None:
        """Collect results for all views.

        Args:
            view_names: List of view names to query
            document_id: Document ID to filter by

        Returns:
            Dictionary mapping view names to their results or the single table if only one view.
        """
        results_dict = {}
        for view_name in view_names:
            sql = f"SELECT * FROM {PROJECT_NAME}.{view_name} where document_id = $document_id"
            results = self._context.datasource.execute_sql(sql, params={"document_id": document_id})
            results_dict[view_name] = results.to_table() if results else None

        # If only one view, return the table directly for automatic DataFrame conversion
        if len(view_names) == 1:
            return results_dict[view_names[0]] or None

        return results_dict

    def ingest(
        self,
        file_name: str,
        data_model_name: str,
        layout_name: str,
    ) -> dict[str, Any]:
        """Ingest document into data model using layout.

        This function creates PERSISTENT state by storing the document, extracted content,
        and transformed content in the database.

        Args:
            file_name: PDF file name to process
            data_model_name: Data model name for document
            layout_name: Document layout to use for processing

        Returns:
            Dict with created document containing extracted and transformed content

        Raises:
            DocumentServiceError: If document processing fails
        """
        data_model_name = normalize_name(data_model_name)
        layout_name = normalize_name(layout_name)

        try:
            data_model = DataModel.find_by_name(self._context.datasource, data_model_name)
            if not data_model:
                raise DocumentServiceError(f"Data model {data_model_name} not found")

            layout = DocumentLayout.find_by_name(
                self._context.datasource, data_model_name, layout_name
            )
            if not layout:
                raise DocumentServiceError(f"Document layout does not exist: {layout_name}")

            if not layout.extraction_schema:
                raise DocumentServiceError(f"Layout {layout_name} has no extraction schema")
            if not layout.translation_schema:
                raise DocumentServiceError(f"Layout {layout_name} has no translation schema")

            parsed_extraction_schema, parsed_translation_schema = validate_and_parse_schemas(
                layout.extraction_schema, layout.translation_schema
            )

            response = self._process_with_experiments(
                file_name=file_name,
                data_model=data_model,
                layout_name=layout_name,
                parsed_extraction_schema=parsed_extraction_schema,
                parsed_translation_schema=parsed_translation_schema,
                data_model_prompt=data_model.prompt,
                model_base_config=data_model.base_config,
                layout_extraction_config=layout.extraction_config,
                layout_prompt=layout.system_prompt,
            )

            # TODO do not return bare dicts.
            return response.model_dump()

        except Exception as e:
            raise DocumentServiceError(f"Failed to process document: {e!s}") from e

    def extract_with_schema(
        self,
        params: ExtractAndTransformContentParams,
    ) -> dict[str, Any]:
        """Extract, transform, validate content with automatic retry and schema storage.

        This function performs the complete document processing pipeline:
        1. Extract and transform content using provided schemas
        2. Validate the processed document
        3. If validation fails, automatically retry with different configurations
        4. Store successful schemas in database for future use

        Args:
            sema4_api_key: Sema4.ai cloud backend API key
            params: ExtractAndTransformContentParams object containing:
                - file_name: file name to process
                - extraction_schema: Extraction schema as JSON string (must be valid JSON)
                - translation_schema: Translation schema as dict with "rules" key containing
                    array of mapping rules
                - data_model_name: Data model name for document
                - layout_name: Document layout to use for processing
            datasource: Document intelligence data source connection

        Returns:
            Response with created document containing extracted and transformed content,
            validation results, and retry information if applicable.

        Raises:
            DocumentServiceError: If document processing fails after all retry attempts
        """
        data_model = DataModel.find_by_name(self._context.datasource, params.data_model_name)
        if not data_model:
            raise DocumentServiceError(f"Data model {params.data_model_name} not found")

        # Validate and parse schemas
        parsed_extraction_schema, parsed_translation_schema = validate_and_parse_schemas(
            params.extraction_schema, params.translation_schema
        )

        response = self._process_with_experiments(
            file_name=params.file_name,
            data_model=data_model,
            layout_name=params.layout_name,
            parsed_extraction_schema=parsed_extraction_schema,
            parsed_translation_schema=parsed_translation_schema,
            data_model_prompt=data_model.prompt,
            model_base_config=data_model.base_config,
            layout_extraction_config=None,
            layout_prompt=None,
        )

        return response.model_dump()

    def validate(self, data_model: DataModel, document_id: str) -> ValidationSummary:
        """Validate a document against quality checks.

        Args:
            data_model_name: The name of the data model
            document_id: The ID of the document to validate
            datasource: The document intelligence data source connection

        Returns:
            Response containing validation results with overall status and rule outcomes

        Raises:
            DocumentServiceError: If data model not found, no quality checks exist,
                project creation fails, or validation fails
        """
        # If there are no quality checks, return success to avoid re-processing at higher levels.
        if not data_model.quality_checks:
            logger.warning(f"No quality checks found for data model {data_model.name}")
            return ValidationSummary(
                overall_status="passed",
                results=[],
                passed=0,
                failed=0,
                errors=0,
            )

        # Initialize the objects in MindsDB (project)
        try:
            initialize_dataserver(PROJECT_NAME, data_model.views)
        except Exception as e:
            raise DocumentServiceError(
                "Failed to create the document intelligence data-server project"
            ) from e

        # Parse quality checks - all stored rules should be valid
        quality_checks = [ValidationRule(**rule) for rule in data_model.quality_checks]

        validation_summary = validate_document_extraction(
            document_id, self._context.datasource, quality_checks
        )

        if validation_summary.overall_status == "failed":
            raise DocumentServiceError(
                f"Document validation encountered errors: {validation_summary.model_dump()}"
            )
        return validation_summary

    def _merge_config(self, base_config: dict, user_config: dict | None) -> dict:
        """
        Merge user configuration with default configuration.

        Args:
            base_config: The base configuration for model
            user_config: The configuration from user (can be None)

        Returns:
            Merged configuration with database config overriding default config
        """
        if not user_config:
            return base_config

        def deep_merge(base: dict, override: dict) -> dict:
            """Recursively merge two dictionaries, with override taking precedence."""
            result = base.copy()
            for key, value in override.items():
                # Special handling for fields that should be completely replaced, not merged
                if key in ["schema", "system_prompt"]:
                    result[key] = value
                elif key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        return deep_merge(base_config, user_config)

    def _generate_experiments(
        self,
        initial_extraction_config: dict[str, Any] | None,
        model_base_config: dict[str, Any] | None,
        initial_user_prompt: str | None,
        initial_layout_prompt: str | None,
        max_experiments: int = 6,
    ) -> list[_Experiment]:
        """Generate a prioritized list of experiments to try.

        Args:
            initial_extraction_config: The initial extraction config to try first
            model_base_config: The model base config
            initial_user_prompt: The initial user prompt to use
            initial_layout_prompt: The initial layout prompt to use
            max_experiments: Maximum number of experiments to generate

        Returns:
            List of experiments ordered by priority (default config first, then custom configs)
        """
        experiments = []

        # Merge initial_extraction_config with model_base_config
        merged_initial_config = self._merge_config(
            model_base_config or {}, initial_extraction_config
        )

        experiments.append(
            _Experiment(
                name="default",
                extraction_config=merged_initial_config,
                user_prompt=initial_user_prompt,
                layout_prompt=initial_layout_prompt,
            )
        )

        custom_configs = ReductoConfig.load_config()
        # Filter out configs that match the initial extraction config (no point retrying
        # with same config)
        filtered_configs = {}
        for config_name, config_data in custom_configs.items():
            if initial_extraction_config and _configs_are_equivalent(
                config_data, initial_extraction_config
            ):
                logger.info(
                    f"Skipping config '{config_name}' as it matches the initial extraction config"
                )
                continue
            filtered_configs[config_name] = config_data

        if not filtered_configs:
            logger.info(
                "All custom configs match the initial extraction config, will only try "
                "default configuration"
            )
            return experiments

        logger.info(
            f"Found {len(filtered_configs)} distinct custom Reducto configs to try "
            f"(filtered from {len(custom_configs)} total configs)"
        )

        # Add filtered custom configs as experiments (limit to max_experiments total)
        remaining_slots = max_experiments - len(experiments)
        for config_name, config_data in list(filtered_configs.items())[:remaining_slots]:
            # Merge each custom config with model_base_config
            merged_custom_config = self._merge_config(model_base_config or {}, config_data)
            experiments.append(
                _Experiment(
                    name=f"reducto_{config_name}",
                    extraction_config=merged_custom_config,
                    user_prompt=initial_user_prompt,
                    layout_prompt=None,
                )
            )

        return experiments

    def _process_document_with_schemas(
        self,
        file_name: str,
        data_model: DataModel,
        layout_name: str,
        extraction_schema: ExtractionSchema,
        translation_schema: TranslationSchema,
        user_prompt: str | None = None,
        extraction_config: dict[str, Any] | None = None,
        layout_prompt: str | None = None,
    ) -> Document:
        """Helper function to process document with extraction and translation schemas.

        Args:
            file_name: Name of the file
            data_model: Data model for document
            layout_name: Document layout name
            extraction_schema: Parsed extraction schema
            translation_schema: Parsed translation schema
            user_prompt: Optional user prompt for processing
            extraction_config: Optional Reducto extraction configuration
            layout_prompt: Optional layout prompt

        Returns:
            Processed document instance

        Raises:
            DocumentServiceError: If document processing fails
        """
        assert self._context.agent_server_transport is not None
        assert self._context.extraction_service is not None

        try:
            # Generate document ID
            pdf_path = self._context.agent_server_transport.get_file(file_name)

            document_id = compute_document_id(pdf_path)
            logger.info(f"Generated document ID: {document_id}")

            # Check if document already exists
            document = Document.find_by_id(self._context.datasource, document_id)
            if not document:
                # Create new document
                document = Document(
                    id=document_id,
                    document_name=file_name,
                    data_model=data_model.name,
                    document_layout=layout_name,
                )
                document.insert(self._context.datasource)
            else:
                # Update existing document
                document.document_layout = layout_name
                document.data_model = data_model.name
                document.document_name = file_name
                document.update(self._context.datasource)

            # Extract content using Reducto
            extraction_results = self._context.extraction_service.extract_with_data_model(
                pdf_path,
                extraction_schema,
                user_prompt,
                extraction_config,
                layout_prompt,
            )
            extracted_content = extraction_results.results
            logger.info("Content extracted successfully")

            # Update document with extracted content
            document.extracted_content = extracted_content
            document.update(self._context.datasource)

            # Transform content using translation schema
            transformed_content = transform_content(
                TransformDocumentLayout(), extracted_content, translation_schema
            )

            # Check if transformed content is empty
            if not transformed_content:
                raise DocumentServiceError(
                    "Transformation resulted in empty content. Please check the translation "
                    "rules and extracted content."
                )

            logger.info("Content transformed successfully")

            # Update document with transformed content
            document.translated_content = transformed_content
            document.update(self._context.datasource)

            return document

        except Exception as e:
            logger.error(f"Error in document processing: {e!s}")
            raise DocumentServiceError(f"Document processing failed: {e!s}") from e

    def _execute_experiment(
        self,
        experiment: _Experiment,
        file_name: str,
        data_model: DataModel,
        layout_name: str,
        parsed_extraction_schema: dict[str, Any],
        parsed_translation_schema: dict[str, Any],
    ) -> _ExperimentResult:
        """Execute a single processing experiment.

        Args:
            experiment: The experiment configuration to execute
            file_name: Name of the file to process
            data_model: Data model for document
            layout_name: Document layout name
            parsed_extraction_schema: Parsed extraction schema
            parsed_translation_schema: Parsed translation schema

        Returns:
            ExperimentResult with success/failure information and error details
        """
        logger.info(f"Starting experiment: {experiment.name}")

        document = None
        validation_results = None
        try:
            # Process document with the experiment's configuration
            document = self._process_document_with_schemas(
                file_name=file_name,
                data_model=data_model,
                layout_name=layout_name,
                extraction_schema=parsed_extraction_schema,
                translation_schema=parsed_translation_schema,
                user_prompt=experiment.user_prompt,
                extraction_config=experiment.extraction_config,
                layout_prompt=experiment.layout_prompt,
            )

            validation_results = self._validate_and_store_schemas(
                data_model,
                document,
                parsed_extraction_schema,
                parsed_translation_schema,
                experiment.extraction_config,
            )

            logger.info(f"Experiment {experiment.name} succeeded")
            return _ExperimentResult(
                document=document,
                experiment_name=experiment.name,
                success=True,
                validation_results=validation_results,
            )

        except Exception as e:
            logger.info(f"Experiment {experiment.name} failed: {e}")
            return _ExperimentResult(
                document=document,
                experiment_name=experiment.name,
                success=False,
                error_message=f"{type(e).__name__}: {e!s}",
            )

    def _validate_and_store_schemas(
        self,
        data_model: DataModel,
        document: Document,
        parsed_extraction_schema: dict[str, Any],
        parsed_translation_schema: dict[str, Any],
        config_data: dict[str, Any] | None = None,
    ) -> ValidationSummary:
        """Validate document and store schemas on success.

        Args:
            document: Document to validate
            datasource: Data source connection
            parsed_extraction_schema: Parsed extraction schema
            parsed_translation_schema: Parsed translation schema
            config_data: Optional config data for retry scenarios

        Returns:
            Dict with validation results

        Raises:
            DocumentServiceError: If validation fails
        """
        validation_response = self.validate(data_model, document.id)

        # Validation passed - store schemas
        DocumentLayout.upsert_schema(
            self._context.datasource,
            document.data_model,
            document.document_layout,
            parsed_extraction_schema,
            parsed_translation_schema,
            config_data,
        )

        return validation_response

    def _process_with_experiments(
        self,
        file_name: str,
        data_model: DataModel,
        layout_name: str,
        parsed_extraction_schema: dict[str, Any],
        parsed_translation_schema: dict[str, Any],
        data_model_prompt: str | None,
        model_base_config: dict[str, Any] | None,
        layout_extraction_config: dict[str, Any] | None,
        layout_prompt: str | None,
    ) -> _ProcessingResponse:
        """Process document by trying experiments until one succeeds.

        Args:
            file_name: Name of the file to process
            data_model: Data model for document
            layout_name: Document layout name
            parsed_extraction_schema: Parsed extraction schema
            parsed_translation_schema: Parsed translation schema
            data_model_prompt: Optional data model prompt for processing
            model_base_config: Optional Base Reducto extraction configuration
            layout_extraction_config: Optional layout Reducto extraction configuration
            layout_prompt: Optional layout prompt/system prompt

        Returns:
            ProcessingResponse with experiment results and final document

        Raises:
            DocumentServiceError: If all experiments fail
        """
        # Generate experiments to try
        experiments = self._generate_experiments(
            initial_extraction_config=layout_extraction_config,
            model_base_config=model_base_config,
            initial_user_prompt=data_model_prompt,
            initial_layout_prompt=layout_prompt,
        )

        logger.info(f"Generated {len(experiments)} experiments to try")

        experiment_results = []
        for experiment in experiments:
            result: _ExperimentResult = self._execute_experiment(
                experiment=experiment,
                file_name=file_name,
                data_model=data_model,
                layout_name=layout_name,
                parsed_extraction_schema=parsed_extraction_schema,
                parsed_translation_schema=parsed_translation_schema,
            )

            experiment_results.append(result)

            if result.success:
                return _ProcessingResponse(
                    success=True,
                    document=result.document,
                    experiments=experiment_results,
                    successful_experiment=experiment.name,
                    total_attempts=len(experiment_results),
                )

        # All experiments failed
        failed_experiment_names = [r.experiment_name for r in experiment_results]
        error_message = (
            f"Document processing failed after {len(experiment_results)} experiments. "
            f"Tried experiments: {', '.join(failed_experiment_names)}. "
        )

        logger.error(error_message)
        raise DocumentServiceError(error_message)

    def _add_document(
        self,
        file_name: str,
        extracted_content: dict[str, Any],
        data_model_name: str,
        *,
        skip_validation: bool = False,
        layout_name: str = DEFAULT_LAYOUT_NAME,
    ) -> Document:
        """
        Adds a previously-extracted document to a DataModel. Callers should use the `ingest`
        function unless they know better.

        Args:
            file_name: PDF file name to process
            data_model_name: Data model name for document
            layout_name: Document layout to use for processing

        Returns:
            The resulting Document.

        Raises:
            DocumentServiceError: If document processing fails
        """
        data_model_name = normalize_name(data_model_name)
        layout_name = normalize_name(layout_name or "default")

        try:
            data_model = DataModel.find_by_name(self._context.datasource, data_model_name)
            if not data_model:
                raise DocumentServiceError(f"Data model {data_model_name} not found")

            layout = DocumentLayout.find_by_name(
                self._context.datasource, data_model_name, layout_name
            )
            if not layout:
                raise DocumentServiceError(f"Document layout does not exist: {layout_name}")

            if not layout.extraction_schema:
                raise DocumentServiceError(f"Layout {layout_name} has no extraction schema")
            if not layout.translation_schema:
                raise DocumentServiceError(f"Layout {layout_name} has no translation schema")

            # Since this is coming from the caller, we should try to validate what they gave us
            # to make sure it matches the intended schema.
            if not skip_validation:
                _validate_extracted_document(extracted_content, layout.extraction_schema)

            # Transform content using translation schema for the default layout (should be no-op)
            transformed_content = transform_content(
                TransformDocumentLayout(), extracted_content, layout.translation_schema
            )

            # Check if transformed content is empty
            if not transformed_content:
                raise DocumentServiceError(
                    "Transformation resulted in empty content. Please check the translation "
                    "rules and extracted content."
                )

            # Check if document already exists
            document_id = self.document_id(file_name)
            document = Document.find_by_id(self._context.datasource, document_id)
            if not document:
                # Create new document
                document = Document(
                    id=document_id,
                    document_name=file_name,
                    data_model=data_model.name,
                    document_layout=layout_name,
                    extracted_content=extracted_content,
                    translated_content=transformed_content,
                )
                document.insert(self._context.datasource)
            else:
                # Update existing document
                document.document_layout = layout_name
                document.data_model = data_model.name
                document.document_name = file_name
                document.extracted_content = extracted_content
                document.translated_content = transformed_content
                document.update(self._context.datasource)

            return document

        except Exception as e:
            logger.error(f"Failed to add document: {e!s}", exc_info=e)
            raise DocumentServiceError(f"Failed to add document: {e!s}") from e


def _configs_are_equivalent(config1: dict[str, Any], config2: dict[str, Any]) -> bool:
    """Compare two extraction configs to determine if they are functionally equivalent.

    Args:
        config1: First config to compare
        config2: Second config to compare

    Returns:
        True if configs are equivalent, False otherwise
    """
    # Handle None cases
    if config1 is None and config2 is None:
        return True
    if config1 is None or config2 is None:
        return False

    # Deep comparison of config dictionaries
    try:
        return config1 == config2
    except Exception:
        # Fallback to string comparison if direct comparison fails
        return str(config1) == str(config2)


def _validate_extracted_document(
    extracted_content: dict[str, Any], extraction_schema: ExtractionSchema
) -> None:
    """Validates an extracted document against a DataModel prior to adding it
    directly. This is a sanity check over the user-input prior to accepting any
    content and writing it to our database (i.e. not using `ingest`).

    Args:
        extracted_content: The extracted content to validate
        extraction_schema: The extraction schema from a DataModel's Layout.

    Raises:
        DocumentServiceError: If the extracted document doesn't match the DataModel.
    """
    import jsonschema

    # Parse the extraction schema
    try:
        validator = jsonschema.Draft7Validator(extraction_schema)
    except Exception as e:
        logger.error(f"Failed to parse extraction schema as JSON schema: {e!s}", exc_info=e)
        raise DocumentServiceError(f"DataModel schema is invalid: {e!s}") from e
    try:
        validator.validate(extracted_content)
    except Exception as e:
        logger.error(
            f"Failed to validate extracted document against extraction schema: {e!s}",
            exc_info=e,
        )
        raise DocumentServiceError(
            f"Failed to validate extracted document against DataModel: {e!s}"
        ) from e
