import json
import logging
import re
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mindsdb_sql import parse_sql
from sema4ai.data import DataSource

from sema4ai_docint.agent_server_client.schema_validation import (
    validate_json_extraction_schema,
)
from sema4ai_docint.models.constants import DEFAULT_LAYOUT_NAME
from sema4ai_docint.utils import ReservedSQLKeywords

from ..models import DataModel
from ..validation import gather_view_metadata_with_samples
from .docx_to_markdown import docx_to_markdown_txt
from .exceptions import DocumentClassificationError
from .models import View
from .prompts import (
    DOCUMENT_LAYOUT_CLASSIFICATION_SYSTEM_PROMPT,
    GENERATE_LAYOUT_NAME_CANDIDATES_SYSTEM_PROMPT,
    NL_QUERY_SYSTEM_PROMPT,
    SUMMARIZE_SYSTEM_PROMPT,
    VALIDATION_RULES_SYSTEM_PROMPT,
    get_schema_prompt,
)
from .transport import (
    DirectTransport,
    HTTPTransport,
    ResponseMessage,
    TransportBase,
)
from .transport._utils import call_transport_method

if TYPE_CHECKING:
    from reducto.types.shared.parse_response import ParseResponse

logger = logging.getLogger(__name__)


def _trim_json_markup(text: str) -> str:
    """
    Trim the JSON markup from the text.
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text


class CategorizedSummary:
    """
    A summary and its corresponding category.
    """

    def __init__(self, summary: str, category: str):
        self.summary = summary
        self.category = category


class AgentServerClient:
    def __init__(
        self,
        agent_id: str | None = None,
        transport: TransportBase | DirectTransport | None = None,
    ):
        """Initialize the AgentServerClient.

        Args:
            agent_id: Optional agent_id to use. If not provided, will attempt to get from
                transport context.
            transport: Optional transport implementation. Can be either:
                - TransportBase: Full transport for HTTP/Memory communication
                - DirectTransport: Minimal transport for direct in-process communication
                If not provided, HTTPTransport will be used.
        """
        # Initialize transport first
        if transport is None:
            # Default to HTTP transport
            self.transport = HTTPTransport(agent_id=agent_id)
        else:
            self.transport = transport

        # TODO: Does anyone use api_url or is_cloud outside of the client and tests?

        # Initialize the transport (only if it has connect method)
        # DirectTransport doesn't need connect/disconnect
        # TODO: Should we do this more lazily?
        if isinstance(self.transport, TransportBase):
            self.transport.connect()

    @staticmethod
    def extract_text_content(response: ResponseMessage) -> str:
        """
        Extract text content from an agent server response. Assumes there is one content item
        and that it is a TextContent object.

        Args:
            response: ResponseMessage from agent server

        Returns:
            str: The text content from the response

        Raises:
            ValueError: If no text content is found in the response
        """
        if not response.content:
            raise ValueError("No content in response from agent server")

        # Find the first text content. Be wary to skip reasoning contents.
        text_content = next((c for c in response.content if c.get("kind") == "text"), None)
        if not text_content:
            raise ValueError("No text content in response from agent server")

        # return the "text" attribute
        return str(text_content["text"])

    @classmethod
    def validate_sql_query(cls, query: str, query_name: str) -> tuple[bool, str, str]:
        """Validate a SQL query using SQL parsing.

        Args:
            query: The SQL query to validate
            query_name: Name of the query for logging (e.g., rule name, NL query identifier)

        Returns:
            tuple[bool, str, str]: (is_valid, modified_query, error_message)
            - is_valid: Whether the query meets basic requirements
            - modified_query: The query with any necessary modifications
            - error_message: Error message if validation failed, empty string if valid
        """
        try:
            logger.info(f"Validating query for {query_name}: {query}")

            # Clean up the query first
            cleaned_query = query.strip()

            # Remove any ```<language> code blocks around the response
            if "```" in cleaned_query:
                content_parts = cleaned_query.split("```")
                min_code_block_parts = 2
                if len(content_parts) >= min_code_block_parts:
                    # Get the content part (index 1) and remove any language identifier
                    cleaned_query = content_parts[1].split("\n", 1)[-1].strip()
                else:
                    cleaned_query = query.strip()

            # Remove trailing semicolon and comments
            cleanup_regex = r";(?=\s*--)|(?<=\S)\s*;(?=\s*$)"
            cleaned_query = re.sub(cleanup_regex, "", cleaned_query)

            # Basic validation - check if query is not empty
            if not cleaned_query or not cleaned_query.strip():
                error_msg = f"Query {query_name} has empty query"
                logger.warning(error_msg)
                return False, query, error_msg

            # Attempt to parse the SQL query using mindsdb_sql
            try:
                parse_sql(cleaned_query)
                logger.info(f"SQL parsing validation passed for {query_name}")
            except Exception as parse_error:
                error_msg = f"Query {query_name} failed SQL parsing validation: {parse_error!s}"
                logger.warning(error_msg)
                return False, query, error_msg

            logger.info(f"Query validation passed for {query_name}")
            return True, cleaned_query, ""

        except Exception as e:
            error_msg = f"Error validating query {query_name}: {e!s}"
            logger.warning(error_msg)
            return False, query, error_msg

    def _format_view_reference_data(self, view_reference_data: list[dict] | None) -> str:
        """Format view reference data for inclusion in prompts.

        Args:
            view_reference_data: Optional list of dictionaries containing view reference data

        Returns:
            str: Formatted view reference information string
        """
        if not view_reference_data:
            return ""

        view_reference_info = "\n\nView Reference Data:\n"
        for view_data in view_reference_data:
            view_reference_info += f"\nView name: {view_data['name']}\n"
            if view_data["columns"]:
                view_reference_info += "\nView columns:\n"
                for col in view_data["columns"]:
                    view_reference_info += f"- {col}\n"
            if view_data["sample_data"]:
                view_reference_info += "\nSample records from the view:\n"
                for i, sample_row in enumerate(view_data["sample_data"]):
                    view_reference_info += f"\nRecord {i + 1}:\n"
                    for key, value in sample_row.items():
                        view_reference_info += f"- {key}: {value}\n"

        return view_reference_info

    # TODO: Fix lint issues in this function
    def generate_validation_rules(  # noqa: C901, PLR0915
        self,
        rules_description: str | None,
        data_model: DataModel,
        datasource: DataSource,
        database_name: str = "document_intelligence",
        limit_count: int = 1,
    ) -> list[dict[str, str]]:
        """Generate the validation rules for a use_case in the form of a JSON schema

        Args:
            rules_description: Description of the rules to generate
            data_model: The data model to generate validation rules for
            datasource: The datasource to use to gather view reference data
            database_name: The database name to prefix view names with (defaults to
                "document_intelligence")
            limit_count: The maximum number of validation rules to generate (defaults to 1)

        Returns:
            list[dict[str, str]]: A list of of validation rule

        Raises:
            ValueError: If rule generation fails
        """
        view_reference_data = gather_view_metadata_with_samples(data_model, datasource)
        view_hints_for_llm = []
        for view in data_model.views:
            try:
                view_obj = View(**view)
                # Include column types in the hints
                columns_with_types = [f"{col.name}: {col.type}" for col in view_obj.columns]
                view_hints_for_llm.append(
                    f"View Name: {view_obj.name}\nColumns: {json.dumps(columns_with_types)}"
                )
            except Exception as e:
                logger.warning(f"Skipping invalid view: {e!s}")

        # Add view reference data to the prompt if available
        view_reference_info = self._format_view_reference_data(view_reference_data)

        # Base messages for all attempts
        base_messages = [
            {"kind": "text", "text": f"Use case description: {data_model.description}"},
        ]
        if rules_description:
            base_messages.append(
                {"kind": "text", "text": f"Rules description: {rules_description}"}
            )
        base_messages.append(
            {
                "kind": "text",
                "text": f"Views definitions: \n{json.dumps(view_hints_for_llm)}",
            },
        )

        # Add view reference data to base messages if available
        if view_reference_info:
            base_messages.append({"kind": "text", "text": view_reference_info})

        def payload_generator(temperature: float, error_feedback: str = "") -> dict:
            """Generate payload for validation rules with given temperature and error feedback."""
            messages = base_messages.copy()
            if error_feedback:
                messages.append({"kind": "text", "text": error_feedback})
            # if a description is provided, we don't want to generate a description
            # and vice-versa.
            generate_description = not bool(rules_description)
            # Build conditional bullet for rule_description
            rule_description_bullet = (
                "\n* rule_description: a description of the rule\n"
                if generate_description
                else "\n"
            )
            return {
                "prompt": {
                    "system_instruction": VALIDATION_RULES_SYSTEM_PROMPT.format(
                        database_name=database_name,
                        limit_count=limit_count,
                        rule_description_bullet=rule_description_bullet,
                    ),
                    "messages": [{"role": "user", "content": messages}],
                    "tools": [],
                    "temperature": temperature,
                    "max_output_tokens": 10240,
                },
            }

        # TODO: Fix lint issues in this function
        def validator(llm_resp: str) -> tuple[bool, list[dict[str, str]], str]:  # noqa: C901, PLR0912, PLR0915
            """Validate the LLM response for validation rules."""
            try:
                # Trim JSON markup before parsing
                llm_resp = _trim_json_markup(llm_resp)
                # Parse JSON response
                rules = json.loads(llm_resp)

                # Ensure rules is a list
                if not isinstance(rules, list):
                    logger.warning(f"Rules is not a list, it's {type(rules)}. Converting to list.")
                    if isinstance(rules, dict):
                        rules = [rules]
                    else:
                        logger.error(f"Cannot convert {type(rules)} to list")
                        return False, [], "Invalid response format: not a list or dict"

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from LLM response: {e}")
                logger.error(f"LLM response was: {llm_resp}")
                error_feedback = (
                    f"\n\nPrevious attempt failed to generate valid JSON. "
                    f"Please ensure your response is valid JSON format. Error: {e}"
                )
                return False, [], error_feedback

            if len(rules) < limit_count:
                logger.warning(
                    f"Only {len(rules)} rules were generated, but {limit_count} rules were "
                    "requested."
                )
                return (
                    False,
                    [],
                    f"Only {len(rules)} rules were generated, but {limit_count} rules were "
                    "requested.",
                )

            # Process each rule
            validated_rules = []
            validation_errors = []

            for i, rule in enumerate(rules):
                try:
                    logger.info(f"Processing rule {i}: {rule}")

                    # Ensure rule is a dictionary
                    if not isinstance(rule, dict):
                        logger.warning(f"Rule {i} is not a dictionary: {type(rule)}")
                        continue

                    # Check if this rule has an error message (indicating it cannot be performed)
                    error_message = rule.get("error_message", "")
                    if error_message and error_message.strip():
                        # This rule cannot be performed due to data type mismatch or other issues
                        # Include it in the results with the error message
                        validated_rules.append(rule)
                        logger.info(
                            f"Rule {rule.get('rule_name', 'unnamed')} has error message: "
                            f"{error_message}"
                        )
                        continue

                    query = rule.get("sql_query", "")
                    if not query or not query.strip():
                        logger.warning(f"Rule {i} missing or empty sql_query field")
                        continue

                    # Basic SQL validation - retry for syntax errors
                    is_valid, modified_query, error_msg = self.validate_sql_query(
                        query, rule.get("rule_name", "unnamed")
                    )

                    if is_valid:
                        rule["sql_query"] = modified_query
                        validated_rules.append(rule)
                    else:
                        # Collect error information for retry (SQL syntax errors)
                        validation_errors.append(
                            {
                                "rule_name": rule.get("rule_name", "unnamed"),
                                "query": query,
                                "error": error_msg,
                            }
                        )

                except Exception as e:
                    logger.warning(f"Invalid rule {i} skipped: {e!s}")
                    validation_errors.append(
                        {
                            "rule_name": rule.get("rule_name", "unnamed")
                            if isinstance(rule, dict)
                            else f"rule_{i}",
                            "query": rule.get("sql_query", "")
                            if isinstance(rule, dict)
                            else str(rule),
                            "error": str(e),
                        }
                    )
                    continue

            # If we have validation errors (SQL syntax issues), format them for feedback and retry
            if validation_errors:
                error_feedback = "\n\nPrevious validation errors that need to be fixed:\n"
                for error_info in validation_errors:
                    error_feedback += f"\nRule '{error_info['rule_name']}':\n"
                    error_feedback += f"Query: {error_info['query']}\n"
                    error_feedback += f"Error: {error_info['error']}\n"
                return False, [], error_feedback

            # At this step, we've validated the rules.
            # If a description was provided, we want to inject the description into the rules.
            if rules_description and validated_rules:
                # We also know that if a description was provided, we should have only one rule.
                if len(validated_rules) != 1:
                    logger.warning(
                        "Validation failed: If a description was provided, only one rule should "
                        "be generated."
                    )
                    # Truncate the rules to one
                    # We know it's greater than 1 as validated_rules is not empty
                    validated_rules = validated_rules[:1]
                validated_rules[0]["rule_description"] = rules_description

            # Return the validated rules (including those with error messages for data type issues)
            return True, validated_rules, ""

        return self._generate_with_retry(
            payload_generator=payload_generator,
            validator=validator,
            operation_name="generate_validation_rules",
            # we don't error out if we receive more than we asked for,
            # but we do truncate the results to the limit count
        )[:limit_count]

    def _parse_response_to_content_blocks(
        self, parse_response: "ParseResponse"
    ) -> list[dict[str, Any]]:
        """Convert Reducto ParseResponse to content blocks for LLM consumption.

        Args:
            parse_response: The Reducto ParseResponse

        Returns:
            List of content block dictionaries suitable for LLM messages
        """
        # Our call to parse already guarantees that we have a ResultFullResponse
        result = parse_response.result

        # Extract only the textual content (avoid dumping blocks/bboxes/metadata).
        extracted_text = "\n\n".join(c.content for c in result.chunks if c.content)

        return [
            {
                "kind": "text",
                "text": f"Document content (parsed by Reducto):\n\n{extracted_text}\n\n",
            }
        ]

    def _coerce_file_to_content_blocks(
        self, file_name: str, start_page: int | None = None, end_page: int | None = None
    ) -> list[dict[str, Any]]:
        """Coerce a file to content blocks."""
        if self._supports_image_conversion(file_name):
            content_blocks = self._file_to_images(
                file_name, start_page=start_page, end_page=end_page
            )
        elif (
            self._is_excel_file(file_name)
            or self._is_docx_file(file_name)
            or self._is_text_file(file_name)
        ):
            text_content = self._file_to_text(file_name, start_page=start_page, end_page=end_page)
            content_blocks = [
                {
                    "kind": "text",
                    "text": f"Document text content:\n\n{text_content}\n\n",
                }
            ]
        else:
            file_extension = self._get_file_extension(file_name)
            raise ValueError(f"Unsupported file type: {file_extension}")

        return content_blocks

    def _schema_payload_generator(
        self, base_messages: list[dict[str, Any]], temperature: float, error_feedback: str = ""
    ) -> dict:
        """Payload generator for methods that need to generate or modify a schema."""
        messages = base_messages.copy()
        if error_feedback:
            messages.append({"kind": "text", "text": error_feedback})
        return {
            "prompt": {
                "messages": [
                    {
                        "role": "user",
                        "content": messages,
                    }
                ],
                "tools": [],
                "temperature": temperature,
                "max_output_tokens": 10240,
            },
        }

    def _schema_validator(self, llm_resp: str) -> tuple[bool, dict[str, Any], str]:
        """Validator for methods that need to generate or modify a schema."""
        try:
            resp_text = _trim_json_markup(llm_resp)
            schema = json.loads(resp_text)
        except json.JSONDecodeError as e:
            return (
                False,
                {},
                f"Previous response was not valid JSON. Error: {e!s}. Please provide valid "
                "JSON without markdown formatting.",
            )

        if not isinstance(schema, dict):
            return (
                False,
                {},
                "Top-level must be a JSON object representing a JSON Schema. Please return a "
                "JSON object.",
            )
        is_valid_schema, schema_error = validate_json_extraction_schema(schema)
        if not is_valid_schema:
            logger.error(f"Schema validation failed: {schema_error}")
            return (
                False,
                {},
                f"Previous response was not a valid JSON schema. Error: {schema_error}. "
                "Please generate a valid JSON Schema that follows the specification.",
            )

        # Check that the LLM didn't provide reserved SQL keywords as top-level property names
        # TODO: This covers 80-90% of the risk, but it is possible that a schema could be generated
        # that contains reserved SQL keywords from a combination of properties that are nested
        # (e.g., an object called "current" with a property called "user"), see DIN-631.
        properties = schema.get("properties", {})
        for prop in properties:
            # Nb. this is a trick for compatibility with StrEnum on py3.11.
            if any(m.value == prop for m in ReservedSQLKeywords):
                return (
                    False,
                    {},
                    f"Previous response contained a reserved SQL keyword as a top-level "
                    f"property name: {prop}. Please change it to a different name.",
                )

        return True, AgentServerClient.sanitize_json_schema(schema), ""

    def generate_schema(
        self,
        file_name: str,
        model_schema: str | dict[str, Any] | None = None,
        start_page: int | None = None,
        end_page: int | None = None,
        user_prompt: str | None = None,
        parse_response: "ParseResponse | None" = None,
    ) -> dict[str, Any]:
        """Unified schema generation from a file with optional model schema guidance.

        Coerces input file to prompt-friendly content (images for PDFs/images,
        extracted text for Excel/DOCX/TXT), builds a single robust prompt based on
        the data-model instructions, and generates a validated JSON Schema with a
        top-level type=object using retry and error-feedback.

        Args:
            file_name: Original filename with extension (PDF, TIFF, PNG, JPEG, Excel, DOCX, TXT)
            model_schema: Optional model schema (stringified JSON or dict) to mimic structure
            start_page: Optional starting page number (1-indexed) for page range extraction
            end_page: Optional ending page number (1-indexed) for page range extraction
            user_prompt: Optional user prompt to guide the schema generation
            parse_response: Optional Reducto ParseResponse to use instead of reading the file.
                If provided, this will be used to extract content, supporting all Reducto
                file formats (30+ types including PPTX, CSV, RTF, etc.)

        Returns:
            dict[str, Any]: Sanitized JSON Schema with top-level type=object

        Raises:
            ValueError: If generation fails after retries or validation fails
        """

        # Prepare base instructions
        instructions = get_schema_prompt(mode="create")

        # Build messages progressively
        base_messages: list[dict[str, Any]] = [{"kind": "text", "text": instructions}]

        # Get content blocks - either from parse_response or by reading the file
        if parse_response is not None:
            # Use Reducto parse response (supports all file formats)
            base_messages.extend(self._parse_response_to_content_blocks(parse_response))
        else:
            # Fallback to legacy file reading (limited format support)
            base_messages.extend(
                self._coerce_file_to_content_blocks(
                    file_name, start_page=start_page, end_page=end_page
                )
            )

        # If model schema is provided, add it with guidance to mimic structure
        if model_schema is not None:
            if isinstance(model_schema, dict):
                model_schema_str = json.dumps(model_schema, indent=2)
            else:
                model_schema_str = str(model_schema)
            model_schema_text = (
                "Model Schema (Target Structure):\n\n"
                f"```json\n{model_schema_str}\n```\n\n"
                "Use this model schema as a reference to generate a similar but adapted "
                "extraction schema based on the actual document content."
            )
            base_messages.append({"kind": "text", "text": model_schema_text})

        if user_prompt is not None:
            user_prompt_text = (
                "Additional instructions:\n"
                f"{user_prompt}\n\n"
                "Use these additional instructions to guide the schema generation process."
            )
            base_messages.append({"kind": "text", "text": user_prompt_text})

        max_attempts = 3
        return self._generate_with_retry(
            payload_generator=partial(self._schema_payload_generator, base_messages),
            validator=self._schema_validator,
            max_attempts=max_attempts,
            temperatures=[0.5 + (i * 0.2) for i in range(max_attempts)],
            operation_name="schema_generation",
        )

    def modify_schema(
        self,
        schema: str | dict[str, Any],
        modification_instructions: str,
        file_name: str | None = None,
    ) -> dict[str, Any]:
        """Modify an existing JSON Schema based on provided instructions.

        Takes an existing schema and modifies it according to the provided instructions,
        optionally using a document file for context. Uses the same validation and
        retry logic as schema generation.

        Args:
            schema: The existing JSON Schema to modify (stringified JSON or dict)
            modification_instructions: Instructions describing how to modify the schema
            file_name: Optional filename with extension (PDF, TIFF, PNG, JPEG, Excel, DOCX, TXT)
                      to provide context for the modifications

        Returns:
            dict[str, Any]: Modified and sanitized JSON Schema with top-level type=object

        Raises:
            ValueError: If modification fails after retries or validation fails
        """
        # Prepare base instructions
        instructions = get_schema_prompt(mode="modify")

        # Build messages progressively
        base_messages: list[dict[str, Any]] = [{"kind": "text", "text": instructions}]

        # Add the existing schema
        if isinstance(schema, dict):
            schema_str = json.dumps(schema, indent=2)
        else:
            schema_str = str(schema)

        schema_text = (
            "Existing Schema to Modify:\n\n"
            f"```json\n{schema_str}\n```\n\n"
            "Modification Instructions:\n"
            f"{modification_instructions}\n\n"
            "Apply the above modifications to the existing schema while preserving "
            "its overall structure and any fields not mentioned in the instructions."
        )
        base_messages.append({"kind": "text", "text": schema_text})

        # If a file is provided, add it as context
        if file_name is not None:
            file_context_text = (
                "\nDocument Context:\n"
                "The following document is provided for reference. Use it to understand "
                "the context for the requested modifications if relevant.\n"
            )
            base_messages.append({"kind": "text", "text": file_context_text})
            base_messages.extend(self._coerce_file_to_content_blocks(file_name))

        max_attempts = 3
        return self._generate_with_retry(
            payload_generator=partial(self._schema_payload_generator, base_messages),
            validator=self._schema_validator,
            max_attempts=max_attempts,
            temperatures=[0.5 + (i * 0.2) for i in range(max_attempts)],
            operation_name="schema_modification",
        )

    def _get_file_extension(self, file_name: str) -> str:
        if "." not in file_name:
            raise ValueError(f"No file extension found in filename: {file_name}")

        return file_name.rsplit(".", 1)[1].lower()

    def _is_pdf_file(self, file_name: str) -> bool:
        """Check if file is a PDF."""
        try:
            return self._get_file_extension(file_name) == "pdf"
        except ValueError:
            return False

    def _is_excel_file(self, file_name: str) -> bool:
        """Check if file is an Excel file."""
        try:
            extension = self._get_file_extension(file_name)
            return extension in ["xlsx", "xls"]
        except ValueError:
            return False

    def _is_image_file(self, file_name: str) -> bool:
        """Check if file is an image file (TIFF, PNG, JPEG) - already in image format."""
        try:
            extension = self._get_file_extension(file_name)
            return extension in ["tiff", "tif", "png", "jpeg", "jpg"]
        except ValueError:
            return False

    def _is_docx_file(self, file_name: str) -> bool:
        """Check if file is a DOCX file."""
        try:
            extension = self._get_file_extension(file_name)
            return extension in ["docx", "doc"]
        except ValueError:
            return False

    def _is_text_file(self, file_name: str) -> bool:
        """Check if file is a text file."""
        try:
            extension = self._get_file_extension(file_name)
            return extension in ["txt", "text"]
        except ValueError:
            return False

    def _supports_image_conversion(self, file_name: str) -> bool:
        """Check if file can be converted to images (PDF + image files)."""
        return self._is_pdf_file(file_name) or self._is_image_file(file_name)

    def _excel_to_text(
        self, file_path: Path, start_page: int | None = None, end_page: int | None = None
    ) -> str:
        """Convert an Excel file to text content for processing."""
        try:
            import pandas as pd

            # Read all sheets from Excel file
            excel_file = pd.ExcelFile(file_path)
            output_content = []

            # Determine which sheets to process based on page range
            sheet_names = excel_file.sheet_names
            if start_page is not None or end_page is not None:
                start_idx = (start_page - 1) if start_page is not None else 0
                end_idx = (end_page - 1) if end_page is not None else len(sheet_names)
                sheet_names = sheet_names[start_idx:end_idx]

            # Process selected sheets
            for sheet_name in sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

                # Add sheet header
                output_content.extend([f"SHEET: {sheet_name}", "-" * 30, ""])

                # Convert dataframe to text representation
                df_filled = df.fillna("")

                # Convert each row to text
                for _, row in df_filled.iterrows():
                    row_text = "\t".join(str(cell) for cell in row if str(cell).strip())
                    if row_text.strip():
                        output_content.append(row_text)

                output_content.append("")  # Add blank line between sheets

            return "\n".join(output_content)
        except Exception as e:
            raise ValueError(f"Error processing Excel file: {e!s}") from e

    def _file_to_text(
        self, file_name: str, start_page: int | None = None, end_page: int | None = None
    ) -> str:
        """Convert a file to text content for processing.

        Args:
            file_name: Original filename with extension (Excel, DOCX, TXT)
            start_page: Optional starting page number (1-indexed) for page range extraction
            end_page: Optional ending page number (1-indexed) for page range extraction

        Returns:
            str: The text content from the file

        Raises:
            ValueError: If the file type is not supported or processing fails
        """
        from sema4ai_docint.agent_server_client.transport._utils import get_file_sync

        with get_file_sync(self.transport, file_name) as file_path:
            if self._is_excel_file(file_name):
                return self._excel_to_text(file_path, start_page=start_page, end_page=end_page)
            elif self._is_docx_file(file_name):
                try:
                    return docx_to_markdown_txt(file_path)
                except Exception as e:
                    raise ValueError(f"Error processing DOCX file: {e!s}") from e
            elif self._is_text_file(file_name):
                try:
                    return open(file_path).read()
                except Exception as e:
                    raise ValueError(f"Error processing text file: {e!s}") from e
            else:
                file_extension = self._get_file_extension(file_name)
                raise ValueError(f"Unsupported file type: {file_extension}")

    def create_mapping(self, business_schema: str, extraction_schema: str) -> str:
        """Create a mapping between business schema and extraction schema.

        Args:
            business_schema: The target business schema
            extraction_schema: The source extraction schema

        Returns:
            str: The mapping rules as a JSON string

        Raises:
            ValueError: If the request fails or response is invalid
        """

        payload = {
            "prompt": {
                "system_instruction": """
You are helping the user translate a JSON object in one schema to another. The user will
provide a JSONSchema for the
original object and the JSONSchema for the desired, translated object. Generate a mapping
between the two schemas.

CRITICAL MAPPING RULES:
1. IDENTIFY ARRAYS: Look at the source schema - if a field has "type": "array" or contains
   multiple items, it's an array
2. For array-to-array mapping: Use "source": "source_array[*]" and "target": "target_array"
   with "mode": "flatten"
3. NEVER use `[*]` in the target field - the target should be the array name without
   wildcards
4. When mapping arrays, ALWAYS use "mode": "flatten" to create separate objects for each
   array element
5. Use "extras" to map individual fields from the source array items to the target array
   item fields
6. For non-array fields, do NOT use "mode" or "extras"
7. NESTED PATHS: Use dotted notation for nested target paths (e.g.,
   "Parent.child_field")
8. EXAMINE TARGET SCHEMA: Look at the target schema structure to determine correct
   nested paths

MAPPING RULE STRUCTURE:
"source": a dotted-path which identifies the field in the source object (use [*] for
arrays)
"target": the name of the field in the target object (never use [*])
"transform": [optional] one of "int", "float", "str", and "bool", will cast the
resulting scalar value as the type
"mode": [optional] use "flatten" for array mappings
"extras": [optional] only used when mode="flatten", maps target field names to source field
names within array items

EXAMPLES:

CORRECT - Simple field mapping (non-array):
{
    "source": "old.location.field",
    "target": "new_field"
},
{
    "source": "old.unit.field",
    "target": "numeric_field",
    "transform": "int"
},

CORRECT - Array mapping (array to array):
{
    "mode": "flatten",
    "extras": {
        "item_id": "id",
        "item_name": "name",
        "item_price": "price"
    },
    "source": "source_items[*]",
    "target": "target_items",
    "transform": null
}

CORRECT - Array mapping with parent fields:
{
    "mode": "flatten",
    "extras": {
        "customer_name": "../customer",
        "order_total": "../../total",
        "order_id": "id",
        "order_date": "date"
    },
    "source": "orders[*]",
    "target": "processed_orders",
    "transform": null
}

INCORRECT - Individual array field mappings (DO NOT DO THIS):
{
    "source": "source_items[*].id",
    "target": "target_items.item_id"
}

INCORRECT - Missing [*] in source (when field is an array):
{
    "source": "source_items",
    "target": "target_items"
}

INCORRECT - [*] in target:
{
    "source": "source_items[*]",
    "target": "target_items[*]"
}

IMPORTANT:
1. ALWAYS include all required fields: "mode", "extras", "source", "target",
   "transform"
2. For non-array fields: Set "mode": null, "extras": {}, "transform": null (unless type
   conversion needed)
3. For arrays: Use "mode": "flatten", populate "extras" with field mappings,
   "transform": null
4. CAREFULLY EXAMINE the source schema to identify which fields are arrays (look for
   "type": "array")
5. CAREFULLY EXAMINE the target schema to identify nested object structures and use
   dotted paths
6. Use [*] ONLY for array fields, not for regular object fields
7. NEVER create individual mappings for fields within arrays - use a single array mapping
with extras
8. Map flat source fields to nested target paths when the target schema has nested
objects

Return the array of rules and nothing else. Do not include markdown formatting.
Do not generate anything except the fields described here. Make sure that the "source" fields
exist in the source schema.
""",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "kind": "text",
                                "text": f"""
Source Schema:
{extraction_schema}
Target Schema:
{business_schema}
""",
                            },
                        ],
                    },
                ],
                "tools": [],
                "temperature": 0.0,
                "max_output_tokens": 10240,
            },
        }

        response_msg = call_transport_method(self.transport, "prompts_generate", payload)
        return AgentServerClient.extract_text_content(response_msg)

    @classmethod
    def is_known_schema(cls, schema_name: str, available_schemas: list[str]) -> bool:
        """Check if the schema name is known.

        Args:
            schema_name: The name of the schema
            available_schemas: List of available schema names

        Returns:
            bool: True if the schema name is known, False otherwise
        """
        schema_name = schema_name.lower()
        if schema_name == "unknown":
            return False
        return any(
            schema_name == available_schema.lower() for available_schema in available_schemas
        )

    def _file_to_images(
        self, file_name: str, start_page: int | None = None, end_page: int | None = None
    ) -> list[dict[str, Any]]:
        """Convert PDF or image files to base64 encoded images.

        Args:
            file_name: Original filename with extension (PDF or image file)
            start_page: Optional starting page number (1-indexed) for page range extraction
            end_page: Optional ending page number (1-indexed) for page range extraction

        Returns:
            list: List of image dictionaries with base64 encoded data

        Raises:
            ValueError: If the file type is not supported for image conversion
        """
        from sema4ai_docint.agent_server_client.transport._utils import get_file_sync

        with get_file_sync(self.transport, file_name) as file_path:
            if self._is_pdf_file(file_name):
                return self._pdf_to_images(file_path, start_page=start_page, end_page=end_page)
            elif self._is_image_file(file_name):
                return self._image_file_to_images(
                    file_path, start_page=start_page, end_page=end_page
                )
            else:
                file_extension = self._get_file_extension(file_name)
                raise ValueError(f"Unsupported file type for image conversion: {file_extension}")

    def _image_file_to_images(
        self, file_path: Path, start_page: int | None = None, end_page: int | None = None
    ) -> list[dict[str, Any]]:
        """Convert image files (TIFF, PNG, JPEG) to base64 encoded images.

        Args:
            file_path: Path to the image file (TIFF, PNG, JPEG)
            start_page: Optional starting page number (1-indexed) for page range extraction
            end_page: Optional ending page number (1-indexed) for page range extraction

        Returns:
            list: List of image dictionaries with base64 encoded data
        """
        from base64 import b64encode
        from io import BytesIO

        from PIL import Image

        def to_jpeg(img: Image.Image) -> str:
            buffer = BytesIO()
            img.save(buffer, format="JPEG")
            return b64encode(buffer.getvalue()).decode("utf-8")

        # Open the image file
        with Image.open(file_path) as img:
            # Convert to RGB if necessary (for PNG with transparency, etc.)
            if img.mode in ("RGBA", "LA", "P"):
                converted_img = img.convert("RGB")
            else:
                converted_img = img

            # For multi-page TIFF files, convert each page
            if hasattr(converted_img, "n_frames") and converted_img.n_frames > 1:
                images = []
                # Determine page range
                start_idx = (start_page - 1) if start_page is not None else 0
                end_idx = (end_page - 1) if end_page is not None else converted_img.n_frames - 1

                # Clamp to valid range
                start_idx = max(0, start_idx)
                end_idx = min(converted_img.n_frames - 1, end_idx)

                for frame_idx in range(start_idx, end_idx + 1):
                    converted_img.seek(frame_idx)
                    frame = converted_img.copy()
                    if frame.mode in ("RGBA", "LA", "P"):
                        frame = frame.convert("RGB")
                    images.append(frame)
            # For single-page images, only include if page 1 is in range
            elif (start_page is None or start_page <= 1) and (end_page is None or end_page >= 1):
                images = [converted_img]
            else:
                images = []

        return [
            {
                "kind": "image",
                "value": to_jpeg(img),
                "mime_type": "image/jpeg",
                "sub_type": "base64",
                "detail": "high_res",
            }
            for img in images
        ]

    def _pdf_to_images(
        self, pdf_path: Path, start_page: int | None = None, end_page: int | None = None
    ) -> list[dict[str, Any]]:
        """Convert PDF files to base64 encoded images.

        Args:
            pdf_path: Path to the PDF file
            start_page: Optional starting page number (1-indexed) for page range extraction
            end_page: Optional ending page number (1-indexed) for page range extraction

        Returns:
            list: List of image dictionaries with base64 encoded data
        """
        # Read PDF file bytes
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # Convert PDF to PIL images using PyMuPDF
        from .images import convert_pdf_bytes_to_images

        images = convert_pdf_bytes_to_images(
            pdf_bytes, dpi=200, start_page=start_page, end_page=end_page
        )

        # Make sure we don't send too many images to the agent server (todo Openai's limit is
        # 50mb, what do other providers have?)
        from .images import to_jpeg, truncate_images

        images = truncate_images(images)

        # Sanity check
        if not images:
            raise ValueError(
                "After converting PDF to images and filtering on size, no images were retained"
            )

        return [
            {
                "kind": "image",
                "value": to_jpeg(img),
                "mime_type": "image/jpeg",
                "sub_type": "base64",
                "detail": "high_res",
            }
            for img in images
        ]

    def generate_natural_language_query_on_views(
        self,
        natural_language_query: str,
        views: list[dict[str, str]],
        document_id: str | None = None,
        view_reference_data: list[dict] | None = None,
        database_name: str = "document_intelligence",
    ) -> str:
        """Generate a SQL query from natural language for a use_case.

        Args:
            natural_language_query: The natural language query to convert to SQL
            views: A list of dicts for each created view. Each dict has a "name", "sql", and
                "columns" key.
            document_id: The id of the document to query
            view_reference_data: Optional list of dictionaries containing view reference data
                including column info and sample data
            database_name: The database/project name to prefix view names with (defaults to
                "document_intelligence")

        Returns:
            str: The generated SQL query

        Raises:
            ValueError: If query generation fails or input validation fails
            DocumentClassificationError: If the generated query doesn't meet requirements
        """
        # Input validation
        if not natural_language_query or not natural_language_query.strip():
            raise ValueError("Natural language query cannot be empty")

        # Validate views using Pydantic model
        validated_views = []
        for view_dict in views:
            try:
                view = View(**view_dict)
                validated_views.append(view)
            except Exception as e:
                raise ValueError(f"Invalid view structure: {e!s}") from e

        view_hints_for_llm = []
        for view in validated_views:
            view_hints_for_llm.append(
                f"View Name: {view.name}\nColumns: {json.dumps(view.get_column_names())}"
            )

        # Add view reference data to the prompt if available
        view_reference_info = self._format_view_reference_data(view_reference_data)

        # Build the content list dynamically
        content = [
            {
                "kind": "text",
                "text": f"Natural language query: {natural_language_query}",
            },
            {
                "kind": "text",
                "text": f"Views definitions: \n{json.dumps(view_hints_for_llm)}",
            },
        ]

        # Add document_id to content if it's not None
        if document_id is not None:
            content.append({"kind": "text", "text": f"Document ID: {document_id}"})

        def payload_generator(temperature: float, error_feedback: str = "") -> dict:
            """Generate payload for NL-to-SQL with given temperature and error feedback."""
            messages = content.copy()
            if error_feedback:
                messages.append({"kind": "text", "text": error_feedback})

            return {
                "prompt": {
                    "system_instruction": NL_QUERY_SYSTEM_PROMPT.format(
                        document_id=document_id or "",
                        view_reference_info=view_reference_info,
                        database_name=database_name,
                    ),
                    "messages": [
                        {
                            "role": "user",
                            "content": messages,
                        },
                    ],
                    "tools": [],
                    "temperature": temperature,
                    "max_output_tokens": 10240,
                },
            }

        def validator(llm_resp: str) -> tuple[bool, str, str]:
            """Validate the LLM response for NL-to-SQL query."""
            # Validate the generated query using SQL parsing
            is_valid, modified_query, error_msg = self.validate_sql_query(llm_resp, "NL-to-SQL")
            if not is_valid:
                return False, "", f"Generated SQL query validation failed: {error_msg}"

            return True, modified_query, ""

        return self._generate_with_retry(
            payload_generator=payload_generator,
            validator=validator,
            operation_name="generate_natural_language_query_on_views",
        )

    def classify_document_with_text(self, chunks: list[str], available_schemas: list[str]) -> str:
        """Classify the document to determine which schema to use using text chunks from agent
        server parsing.

        Args:
            chunks: List of text chunks from parsed document (e.g. from Reducto
                ResultFullResultChunk.content)
            available_schemas: List of available schema names to choose from

        Returns:
            str: The matched schema name

        Raises:
            DocumentClassificationError: If the document cannot be classified
            ValueError: If text extraction fails
        """
        if not chunks:
            raise ValueError("No text chunks provided for classification")

        # Create a formatted list of available schemas
        schema_list = "\n".join(f"- {schema.lower()}" for schema in available_schemas)

        # Combine chunks into a single string
        prompt_input = "\n".join(chunks)

        payload = {
            "prompt": {
                "system_instruction": f"""
You are a document classifier. Your task is to analyze the document text and determine which
schema it matches.
Look for a unique identifier in the document text. It might be in a header or footer.
Here are a list of schemas that already exist:
{schema_list}
When possible, choose a schema that already exists. Otherwise, respond with your best
suggestion of a schema name. Don't include temporal information in the schema name like dates.
Only include the schema name in the response, no other text. If you cannot determine any
schema name, respond with "UNKNOWN".
""",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "kind": "text",
                                "text": (
                                    f"Here is the parsed document content:\n\n{prompt_input}\n\n"
                                    + "Determine which schema this document matches from the "
                                    + "available schemas."
                                ),
                            },
                        ],
                    },
                ],
                "tools": [],
                "temperature": 0.0,
                "max_output_tokens": 10240,
            },
        }
        response_msg = call_transport_method(self.transport, "prompts_generate", payload)

        # basic normalization (strip and lower)
        schema_name = AgentServerClient.extract_text_content(response_msg).strip().lower()

        known_schema = AgentServerClient.is_known_schema(schema_name, available_schemas)
        if not known_schema:
            raise DocumentClassificationError(schema_name, available_schemas)

        return schema_name

    def classify_document_with_images(
        self, base64_images: list[str], available_layouts: list[str]
    ) -> str:
        """Classify the document to determine which layout to use using images.

        Args:
            base64_images: List of base64 encoded image strings
            available_layouts: List of available layout names to choose from

        Returns:
            str: The matched layout name

        Raises:
            DocumentClassificationError: If the document cannot be classified
            ValueError: If image processing fails
        """
        if not base64_images:
            raise ValueError("No images provided for classification")

        # Create a formatted list of available layouts
        layout_list = "\n".join(f"- {layout.lower()}" for layout in available_layouts)
        images = [
            {
                "kind": "image",
                "value": img,
                "mime_type": "image/jpeg",
                "sub_type": "base64",
                "detail": "high_res",
            }
            for img in base64_images
        ]
        payload = {
            "prompt": {
                "system_instruction": DOCUMENT_LAYOUT_CLASSIFICATION_SYSTEM_PROMPT.format(
                    layout_list=layout_list
                ),
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            *images,
                            {
                                "kind": "text",
                                "text": (
                                    "Determine which layout name this document matches from "
                                    "the available layouts. The match should be strongly based "
                                    "on direct match of one of the given layout names with "
                                    "logo or label in the image. If not clear, respond with "
                                    "'UNKNOWN'."
                                ),
                            },
                        ],
                    },
                ],
                "tools": [],
                "temperature": 0.0,
                "max_output_tokens": 10240,
            },
        }

        response_msg = call_transport_method(self.transport, "prompts_generate", payload)

        # basic normalization (strip and lower)
        layout_name = AgentServerClient.extract_text_content(response_msg).strip().lower()

        known_layout = AgentServerClient.is_known_schema(layout_name, available_layouts)
        if not known_layout:
            raise DocumentClassificationError(layout_name, available_layouts)

        return layout_name

    def _generate_layout_name_candidates(self, base64_images: list[str]) -> dict[str, float]:
        """Generate 5 potential layout name candidates with confidence scores.

        Args:
            base64_images: List of base64 encoded image strings

        Returns:
            Dict mapping layout name candidates to confidence scores (0.0-1.0)
        """
        if not base64_images:
            raise ValueError("No images provided for layout name generation")

        images = [
            {
                "kind": "image",
                "value": img,
                "mime_type": "image/jpeg",
                "sub_type": "base64",
                "detail": "high_res",
            }
            for img in base64_images
        ]

        # Prepare content
        content = [
            *images,
            {
                "kind": "text",
                "text": (
                    "Generate 5 potential layout names with confidence scores based on the "
                    "provided images."
                ),
            },
        ]

        payload = {
            "prompt": {
                "system_instruction": GENERATE_LAYOUT_NAME_CANDIDATES_SYSTEM_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    },
                ],
                "tools": [],
                "temperature": 0.0,
                "max_output_tokens": 10240,
            },
        }

        response_msg = call_transport_method(self.transport, "prompts_generate", payload)

        response_text = AgentServerClient.extract_text_content(response_msg).strip()
        response_text = _trim_json_markup(response_text)

        try:
            candidates = json.loads(response_text)
            # Validate that all values are valid floats between 0.0 and 1.0
            validated_candidates = {}
            for layout, score in candidates.items():
                if isinstance(score, int | float) and 0.0 <= score <= 1.0:
                    # Normalize layout name (strip and lower)
                    normalized_layout = layout.strip().lower()
                    validated_candidates[normalized_layout] = float(score)
            return validated_candidates
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error parsing layout name candidates JSON: {e}")
            print(f"Response was:\n {response_text}")
            return {}

    def generate_document_layout_name(self, base64_images: list[str], filename: str) -> str:
        """Generate a layout name for a document using multi-candidate approach with filename
        validation.

        Args:
            base64_images: List of base64 encoded image strings
            filename: Filename for validation (mandatory for improved accuracy)

        Returns:
            str: The generated layout name

        Raises:
            ValueError: If image processing fails or filename is empty
        """
        if not base64_images:
            raise ValueError("No images provided for layout name generation")

        if not filename or not filename.strip():
            raise ValueError("Filename is required for layout name generation")

        # Step 1: Generate 5 potential layout name candidates with confidence scores
        candidate_scores = self._generate_layout_name_candidates(base64_images)
        print(f"Image scores: {candidate_scores}")

        if not candidate_scores:
            raise ValueError("Failed to generate layout name candidates")

        # Step 2: Validate candidates with filename similarity
        candidates = list(candidate_scores.keys())
        filename_scores = self._compute_filename_similarity(filename, candidates)
        print(f"Filename scores: {filename_scores}")

        # Step 3: Combine scores with weighted formula
        final_scores = {}
        for candidate in candidates:
            visual_score = candidate_scores.get(candidate, 0.0)
            filename_score = filename_scores.get(candidate, 0.0)

            # Weighted formula: visual_confidence * 0.5 + filename_similarity * 0.5
            final_score = round((visual_score * 0.5) + (filename_score * 0.5), 2)
            final_scores[candidate] = final_score

        print(f"Overall scores: {final_scores}")

        # Return candidate with highest combined score
        best_candidate = max(final_scores.keys(), key=lambda x: final_scores[x])
        return best_candidate

    def summarize(self, file_name: str) -> str:
        """Summarize the document for search retrieval and classification purposes.

        Args:
            file_name: Original filename with extension (PDF, TIFF, PNG, JPEG, Excel)
        Returns:
            str: The document summary
        Raises:
            ValueError: If summarization fails
        """
        content: str | list[dict[str, Any]]

        # Determine file type and prepare content
        if self._supports_image_conversion(file_name):
            # Convert file to images and pass to summarization method
            # Limit to a max of 5 pages to generate the summary
            content = self._file_to_images(file_name, end_page=6)
        elif (
            self._is_excel_file(file_name)
            or self._is_docx_file(file_name)
            or self._is_text_file(file_name)
        ):
            # Extract text from file and pass to summarization method
            content = self._file_to_text(file_name, end_page=6)
        else:
            file_extension = self._get_file_extension(file_name)
            raise ValueError(f"Unsupported file type: {file_extension}")

        return self.gen_summary_from_content(content)

    def gen_summary_from_content(self, content: str | list[dict[str, Any]]) -> str:
        """Generate a summary using the Agent Server with provided content.

        Args:
            content: Either a text string or a list of image dictionaries to send to the
                Agent Server

        Returns:
            str: The document summary

        Raises:
            ValueError: If summarization fails
        """
        # Prepare the content based on type
        if isinstance(content, str):
            # Text content - wrap in content structure with uniform prompt
            formatted_content = [
                {
                    "kind": "text",
                    "text": f"Below is the text content of the document:\n\n{content}\n\n",
                },
            ]
        else:
            # Image content - add instruction text
            formatted_content = [
                {
                    "kind": "text",
                    "text": "Below are screenshots from the document.",
                },
                *content,
            ]

        payload = {
            "prompt": {
                "system_instruction": SUMMARIZE_SYSTEM_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": formatted_content,
                    },
                ],
                "tools": [],
                "temperature": 0.5,
                "max_output_tokens": 10240,
            },
        }

        response_msg = call_transport_method(self.transport, "prompts_generate", payload)

        return AgentServerClient.extract_text_content(response_msg)

    def summarize_with_args(self, args: dict[str, Any]) -> str:
        """Summarize content using flexible arguments that get passed to the LLM.

        Args:
            args: Dictionary of arguments to construct the summarization prompt.
                  The keys and values will be formatted as "key: value" pairs in the prompt.

        Returns:
            str: The generated summary
        """
        # Construct the content text from the args dictionary
        context = []
        for key, value in args.items():
            context.append(f"{key}: {value}")

        payload = {
            "prompt": {
                "system_instruction": SUMMARIZE_SYSTEM_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "kind": "text",
                                "text": "\n\n".join(context),
                            }
                        ],
                    }
                ],
                "tools": [],
                "temperature": 0.5,
                "max_output_tokens": 10240,
            }
        }

        response_msg = call_transport_method(self.transport, "prompts_generate", payload)

        return AgentServerClient.extract_text_content(response_msg)

    def categorize(
        self, known_summaries: list[CategorizedSummary], unknown_summary: str
    ) -> tuple[CategorizedSummary, float]:
        """
        Categorize an unknown summary against a list of known summaries.

        Args:
            known_summaries: List of CategorizedSummary objects
            unknown_summary: The summary to categorize
        """

        payload = {
            "prompt": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            *[
                                {
                                    "kind": "text",
                                    "text": (
                                        f"Categorized summary {i + 1}: {known_summaries[i].summary}"
                                    ),
                                }
                                for i in range(len(known_summaries))
                            ],
                            {
                                "kind": "text",
                                "text": f"Uncategorized summary: {unknown_summary}",
                            },
                            {
                                "kind": "text",
                                "text": (
                                    "Given a list of categorized summaries and an "
                                    "uncategorized summary, output a float between 0.0 and 1.0 "
                                    "reflecting semantic relevance of each, ignoring stylistic "
                                    "similarity. Output the relevancy number for each in order "
                                    "of the categorized summaries, one per line. Do not number "
                                    "the lines. Do not include any other text."
                                ),
                            },
                        ],
                    },
                ],
                "tools": [],
                "temperature": 0.5,
                "max_output_tokens": 10240,
            },
        }

        response_msg = call_transport_method(self.transport, "prompts_generate", payload)

        raw_relevancies = AgentServerClient.extract_text_content(response_msg)

        relevancies = [float(relevancy) for relevancy in raw_relevancies.split("\n")]

        max_relevancy = max(relevancies)
        return known_summaries[relevancies.index(max_relevancy)], max_relevancy

    def _generate_with_retry(
        self,
        payload_generator: callable,
        validator: callable,
        max_attempts: int = 3,
        temperatures: list[float] | None = None,
        operation_name: str = "generation",
    ) -> Any:
        """Generic method to generate content with retry logic and validation.

        Args:
            payload_generator: Function that takes temperature and error_feedback and returns
                payload
            validator: Function that takes the response and returns (is_valid, result,
                error_feedback)
            max_attempts: Maximum number of retry attempts
            temperatures: List of temperatures to try (default: [0.0, 0.3, 0.5])
            operation_name: Name of the operation for logging

        Returns:
            The validated result

        Raises:
            ValueError: If all attempts fail
        """
        if temperatures is None:
            temperatures = [0.0, 0.3, 0.5]

        error_feedback = ""

        for attempt in range(max_attempts):
            temperature = temperatures[min(attempt, len(temperatures) - 1)]
            logger.info(
                f"Attempt {attempt + 1}/{max_attempts} for {operation_name} "
                f"with temperature {temperature}"
            )

            try:
                # Generate payload with current temperature and error feedback
                payload = payload_generator(temperature, error_feedback)

                # Make the request
                response_msg = call_transport_method(self.transport, "prompts_generate", payload)

                # Extract and validate the response
                llm_resp = AgentServerClient.extract_text_content(response_msg)
                logger.info(f"Raw LLM response for {operation_name}: {llm_resp}")

                is_valid, result, error_feedback = validator(llm_resp)

                if is_valid:
                    logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                    return result
                else:
                    logger.warning(
                        f"{operation_name} validation failed on attempt {attempt + 1}: "
                        f"{error_feedback}"
                    )

            except Exception as e:
                logger.warning(f"{operation_name} attempt {attempt + 1} failed: {e!s}")
                error_feedback = f"\n\nPrevious attempt failed with error: {e!s}"

        # If all attempts failed
        raise ValueError(f"Failed to {operation_name} after {max_attempts} attempts")

    # TODO: Fix lint issues in this function
    @staticmethod
    def sanitize_json_schema(schema: dict[str, Any]) -> dict[str, Any]:  # noqa: C901
        """Sanitize the json schema by handling type lists in the schema.

        Args:
            schema: The input json schema

        Returns:
            dict: The sanitized json schema
        """

        def sanitize_property(prop: dict[str, Any]) -> dict[str, Any]:
            """Sanitize a single property in the schema."""
            if "type" in prop:
                prop_type = prop["type"]
                if isinstance(prop_type, list):
                    # Handle array type
                    nullable_type_length = 2
                    if len(prop_type) == nullable_type_length and "null" in prop_type:
                        # Remove null and use the other type
                        non_null_types = [t for t in prop_type if t != "null"]
                        prop["type"] = non_null_types[0]
                    elif len(prop_type) == 1:
                        # Single element array, convert to non-array
                        prop["type"] = prop_type[0]
                    else:
                        raise ValueError("type should be a string, but was a list")
            return prop

        def sanitize_recursive(obj: dict[str, Any]) -> dict[str, Any]:
            """Recursively sanitize the schema."""
            sanitized = {}
            for key, value in obj.items():
                if key == "properties" and isinstance(value, dict):
                    # Sanitize each property
                    sanitized[key] = {
                        k: sanitize_recursive(sanitize_property(v.copy())) for k, v in value.items()
                    }
                elif key == "items" and isinstance(value, dict):
                    # Handle array items
                    sanitized[key] = sanitize_recursive(sanitize_property(value.copy()))
                elif isinstance(value, dict):
                    # Recursively handle nested objects
                    sanitized[key] = sanitize_recursive(value)
                elif isinstance(value, list):
                    # Handle lists that might contain objects
                    sanitized[key] = [
                        sanitize_recursive(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    sanitized[key] = value
            return sanitized

        return sanitize_recursive(schema)

    def _compute_image_based_similarity(
        self, base64_images: list[str], available_layouts: list[str]
    ) -> dict[str, float]:
        """Compute similarity scores between document images and available layout names.

        Args:
            base64_images: List of base64 encoded image strings
            available_layouts: List of available layout names

        Returns:
            Dict mapping layout names to similarity scores (0.0-1.0)
        """
        if not base64_images:
            return {}

        # Create a formatted list of available layouts
        layout_list = "\n".join(f"- {layout.lower()}" for layout in available_layouts)

        images = [
            {
                "kind": "image",
                "value": img,
                "mime_type": "image/jpeg",
                "sub_type": "base64",
                "detail": "high_res",
            }
            for img in base64_images
        ]

        payload = {
            "prompt": {
                "system_instruction": f"""
You are a document layout classifier. Your task is to analyze the document images and
determine which layouts they match.
Here is a list of layout names that already exist:
{layout_list}

Identify the layout names that best match the document by focusing on the document
producer/originator.
Look for visual patterns, logos, company names, and organizational characteristics that
identify who PRODUCED/ORIGINATED the document.

Guidelines:
- Focus on the sender/issuer of the document, not the recipient/customer
- Identify the organization, company, or entity that produced the document
- For invoices: identify the company that issued the invoice
- For receipts: identify the store/merchant that issued the receipt
- For insurance documents: identify the insurance company that issued the policy
- For bank statements: identify the bank that issued the statement
- For tickets: identify the service provider that issued the ticket

Return ONLY the top 5 most similar layouts with similarity scores from 0.0 to 1.0 in
valid JSON format:
{{
    "layout_name1": score,
    "layout_name2": score,
    "layout_name3": score,
    "layout_name4": score,
    "layout_name5": score
}}

The match should be strongly based on direct match of one of the given layout names
with logo or label in the image.
Do not include any markdown formatting or additional text - just the JSON.
Output should only contain existing layout names.
""",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            *images,
                            {
                                "kind": "text",
                                "text": (
                                    "Return the top 5 most similar layouts with scores in JSON "
                                    "format based on visual similarity. Focus on the document "
                                    "producer/originator."
                                ),
                            },
                        ],
                    },
                ],
                "tools": [],
                "temperature": 0.0,
                "max_output_tokens": 10240,
            },
        }

        response_msg = call_transport_method(self.transport, "prompts_generate", payload)

        response_text = AgentServerClient.extract_text_content(response_msg).strip()
        response_text = _trim_json_markup(response_text)

        try:
            scores = json.loads(response_text)
            # Validate that all values are valid floats between 0.0 and 1.0
            validated_scores = {}
            for layout, score in scores.items():
                if isinstance(score, int | float) and 0.0 <= score <= 1.0:
                    validated_scores[layout] = float(score)
            return validated_scores
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error parsing image similarity JSON: {e}")
            print(f"Response was:\n {response_text}")
            return {}

    def _compute_filename_similarity(
        self, doc_name: str, available_layouts: list[str]
    ) -> dict[str, float]:
        """Compute similarity scores between document filename and available layout names.

        Args:
            doc_name: The document filename
            available_layouts: List of available layout names

        Returns:
            Dict mapping layout names to similarity scores (0.0-1.0)
        """
        layout_list = "\n".join(f"- {layout}" for layout in available_layouts)

        payload = {
            "prompt": {
                "system_instruction": """
You are a document classifier. Compare this new document filename against all existing
layout names and provide similarity scores from 0.0 to 1.0.

CRITICAL SCORING RULES:
Assign high scores (>0.5) for existing layout names ONLY when:

1. WORD MAJORITY REQUIREMENT:
   - If layout name has 1 word: that word (or clear variation) must appear in filename
   - If layout name has 2+ words: majority of words must appear in filename
   - Example: layout "company_invoice" requires both "company" AND "invoice" in filename

2. CONFLICTING NAME DETECTION:
   - If filename contains a different entity name than the layout name, score must be ≤0.3
   - Example: "Acme Corp" in filename conflicts with "beta_systems" layout

3. VARIATIONS ALLOWED:
   - Accept common abbreviations and variations (e.g., "corp" for "corporation",
     "inc" for "incorporated")
   - Accept singular/plural forms (e.g., "system" for "systems")
   - Accept underscore/space/hyphen variations (e.g., "beta_systems" matches "Beta Systems")

4. INSUFFICIENT FOR HIGH SCORES:
   - Document type similarity (both invoices, statements, receipts, etc.)
   - Industry similarity (both banks, retailers, manufacturers, etc.)
   - General naming pattern similarity
   - Date format similarities

5. ENTITY NAME FOCUS:
   - Prioritize matching the primary entity/organization name in the layout
   - Secondary keywords (like document types) are less important for scoring

Focus on EXACT entity name matching, not semantic, industry, or document type similarity.

Return ONLY the top 5 most similar layouts with scores in valid JSON format:
{
    "layout_name1": score,
    "layout_name2": score,
    "layout_name3": score,
    "layout_name4": score,
    "layout_name5": score
}

Do not include any markdown formatting or additional text - just the JSON.
""",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "kind": "text",
                                "text": f"""
NEW DOCUMENT FILENAME:
{doc_name}

EXISTING LAYOUT NAMES:
{layout_list}

Return the top 5 most similar layouts with scores in JSON format.
Output should only contain existing layout names.
""",
                            },
                        ],
                    },
                ],
                "tools": [],
                "temperature": 0.0,
                "max_output_tokens": 10240,
            },
        }

        response_msg = call_transport_method(self.transport, "prompts_generate", payload)

        response_text = AgentServerClient.extract_text_content(response_msg).strip()
        response_text = _trim_json_markup(response_text)

        try:
            scores = json.loads(response_text)
            # Validate that all values are valid floats between 0.0 and 1.0
            validated_scores = {}
            for layout, score in scores.items():
                if isinstance(score, int | float) and 0.0 <= score <= 1.0:
                    validated_scores[layout] = float(score)

            return AgentServerClient._update_filename_scores(validated_scores)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error parsing filename similarity JSON: {e}")
            print(f"Response was:\n {response_text}")
            return {}

    def classify_document_multi_signal(
        self, base64_images: list[str], available_layouts: list[str], doc_name: str
    ) -> str:
        """Classify document using multi-signal weighted scoring approach (image + filename only).

        Args:
            doc_name: Document filename
            available_layouts: List of available layout names
            base64_images: List of base64 encoded image strings

        Returns:
            str: Best matching layout name or raise DocumentClassificationError
        """
        if not available_layouts:
            raise DocumentClassificationError("Unknown", available_layouts)

        # Compute similarity scores for image and filename signals only
        image_scores = self._compute_image_based_similarity(base64_images, available_layouts)
        print(f"Image scores: {image_scores}")
        filename_scores = self._compute_filename_similarity(doc_name, available_layouts)
        print(f"Filename scores: {filename_scores}")

        # Combine all unique layout names from both signals
        all_layouts = set(image_scores.keys()) | set(filename_scores.keys())

        # Calculate weighted final scores (image + filename only)
        final_scores = {}
        for layout in all_layouts:
            image_score = image_scores.get(layout, 0.0)
            filename_score = filename_scores.get(layout, 0.0)

            # Weighted formula: image * 0.6 + filename * 0.4
            final_score = round((image_score * 0.6) + (filename_score * 0.4), 2)
            final_scores[layout] = final_score

        print(f"Final scores: {final_scores}")

        # Find best match
        if not final_scores:
            raise DocumentClassificationError("Unknown", available_layouts)

        best_layout = max(final_scores.keys(), key=lambda x: final_scores[x])
        best_score = final_scores[best_layout]

        if not AgentServerClient.is_known_schema(best_layout, available_layouts):
            raise DocumentClassificationError(best_layout, available_layouts)

        # Apply threshold (0.7 = 70% of Maximum Possible Score i.e. 1.0)
        classification_threshold = 0.7
        if best_score >= classification_threshold:
            return best_layout
        else:
            raise DocumentClassificationError("Unknown", available_layouts)

    @staticmethod
    def _update_filename_scores(filename_scores: dict[str, float]) -> dict[str, float]:
        """Update the filename scores to give the "default" layout a perfect score to avoid
        negatively impacting the final score.

        Args:
            filename_scores: Dict mapping layout names to filename similarity scores

        Returns:
            Dict mapping layout names to filename similarity scores
        """
        # Give the "default" layout a perfect score to avoid negatively impacting the final score.
        # The "default" layout name is statically chosen. We want to encourage re-use of the default
        # layout
        if DEFAULT_LAYOUT_NAME in filename_scores:
            filename_scores[DEFAULT_LAYOUT_NAME] = 1.0

        return filename_scores
