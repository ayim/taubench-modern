"""Module for parsing CLI arguments associated with Agent Server configuration."""

import sys
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import yaml

from agent_platform.core.configurations.representers import (
    BUILT_IN_REPRESENTERS,
    Representer,
    get_representer_for_field,
)
from agent_platform.server.agent_architectures import AgentArchManager
from agent_platform.server.cli.args import ServerArgs
from agent_platform.server.configuration_manager import (
    ConfigurationService,
)
from agent_platform.server.constants import (
    DEFAULT_CONFIG_FILE_NAME,
    default_config_path,
)

if TYPE_CHECKING:
    from agent_platform.server.configuration_manager import ConfigurationManager

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

INDENT = 2


def get_config_path(config_path: PathLike | None) -> Path:
    """Get the configuration path from the CLI arguments."""
    if config_path is None:
        return default_config_path()
    return Path(config_path)


def parse_config_path_args(
    args: ServerArgs,
    exit_on_error: bool = False,
) -> tuple[Path, bool]:
    """Check the configuration arguments, returning the parsed config path
    and whether it exists.

    Args:
        args: The CLI arguments.
        exit_on_error: Whether to exit the program on error.

    Returns:
        The parsed config path and whether it exists.
    """
    if args.config_path is None:
        config_path = default_config_path()
    else:
        config_path = get_config_path(args.config_path)
    is_config_path = config_path.exists()
    if not is_config_path:
        logger.error(f"Configuration file not found: {config_path}")
        if exit_on_error:
            sys.exit(1)
    return config_path, is_config_path


def load_full_config(
    load_trusted_architectures: bool = True,
    additional_packages: list[str] | None = None,
) -> None:
    """Load the full configuration.

    Args:
        load_trusted_architectures: Whether to load trusted architectures.
        additional_packages: Additional packages to scan for configurations.
    """
    manager = ConfigurationService.get_instance()
    if additional_packages is None:
        additional_packages = []
    packages_to_scan = [
        "agent_platform.core",
        "agent_platform.server",
        *additional_packages,
    ]
    if load_trusted_architectures:
        arch_manager = AgentArchManager(
            wheels_path="./todo-for-out-of-process/wheels",
            websocket_addr="todo://think-about-out-of-process",
        )
        packages_to_scan.extend(
            [name for name, _ in arch_manager.in_process_allowlist],
        )
    # TODO: add out-of-process architectures
    manager.reload(packages_to_scan=packages_to_scan)


def print_config(
    should_exit: bool = True,
    export_path: PathLike | bool | None = None,
) -> None:
    """Print the configuration in YAML format with helpful comments.

    Args:
        should_exit: Whether to exit after printing the configuration.
        export_path: Path to save the configuration to. If None, print to stdout.
                    If a directory, the default filename will be used.
    """
    load_full_config()
    manager = ConfigurationService.get_instance()
    all_representers: list[type[Representer]] = [*BUILT_IN_REPRESENTERS]
    for cls in manager.config_classes.values():
        for field in cls.get_fields():
            representer = get_representer_for_field(field)
            if representer and representer not in all_representers:
                all_representers.append(representer)
    for representer in all_representers:
        representer.register_representer()

    # Get the configuration data without derived fields.
    complete_config = manager.get_complete_config(include_fields_with_no_init=False)

    # Add YAML document header with usage information as comments
    config_header = [
        "# Agent Server Configuration File",
        "#",
        "# This YAML file contains configuration settings for the "
        "Sema4.ai Agent Server.",
        "#",
        "# Configuration file lookup order:",
        "# 1. Path specified by SEMA4AI_AGENT_SERVER_CONFIG_PATH environment variable",
        "# 2. SEMA4AI_AGENT_SERVER_HOME/agent-server-config.yaml",
        "# 3. SEMA4AI_STUDIO_HOME/agent-server-config.yaml",
        "# 4. Current working directory",
        "#",
        "# Usage Notes:",
        "# - You only need to specify the settings you want to override",
        "# - Default values will be used for any unspecified settings",
        "# - Configuration changes require restarting the server",
        "# - For development/testing, use the --config-path argument "
        "for custom locations",
        "#",
        f"# Configuration file expected at: {manager.config_path}",
        "",
    ]

    # Format the configuration as YAML with comments for each field
    yaml_str = generate_yaml_with_comments(complete_config, manager)

    # Combine header and YAML content
    full_config = "\n".join(config_header) + "\n" + yaml_str

    # Write to file or print to stdout
    if export_path is True:
        print(full_config)
    elif export_path is not False and export_path is not None:
        # Convert to Path object for easier manipulation
        path = Path(export_path)

        # If the path is a directory, use the default filename
        if path.is_dir():
            path = path / DEFAULT_CONFIG_FILE_NAME

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write the configuration to the file
        with open(path, "w") as f:
            f.write(full_config)
        logger.info(f"Configuration exported to {path}")

    if should_exit:
        sys.exit(0)


def _wrap_single_line(description: str, indent: int, max_length: int) -> str:
    """Wrap a single line of text to fit within a maximum length.

    Args:
        description: The text to wrap
        indent: The indentation level
        max_length: The maximum line length

    Returns:
        A wrapped string with proper indentation and comment prefix
    """
    if not description:
        return f"{indent * ' '}#"

    # Calculate effective max length accounting for indent and comment prefix
    effective_max_length = max_length - indent - 2  # 2 for "# "

    if len(description) <= effective_max_length:
        return f"{indent * ' '}# {description}"

    wrapped = []
    current_line = ""

    for word in description.split():
        if not current_line:
            # First word on the line
            if len(word) <= effective_max_length:
                current_line = word
            else:
                # Handle case where a single word is longer than the line
                wrapped.append(word)
                current_line = ""
        elif len(current_line) + len(word) + 1 <= effective_max_length:
            current_line += " " + word
        else:
            wrapped.append(current_line)
            current_line = word

    if current_line:
        wrapped.append(current_line)

    # Add proper indentation and comment prefix to each line
    prefix = " " * indent + "# "
    return "\n".join(prefix + line for line in wrapped)


def _process_multiline_description(
    description: str,
    indent: int,
    max_length: int,
) -> list[str]:
    """Process a description with embedded line returns.

    Args:
        description: The text to process
        indent: The indentation level
        max_length: The maximum line length

    Returns:
        A list of wrapped strings
    """
    if not description:
        return []

    # Normalize the description by stripping leading/trailing whitespace
    # and handling both cases (with or without leading newline)
    normalized_description = description.strip()
    if not normalized_description:
        return [f"{indent * ' '}#"]

    # Split into lines and process
    lines = normalized_description.split("\n")
    result = []
    current_paragraph = []
    first_line_indent = 0  # Initialize with a default of 0 to avoid None
    in_new_paragraph = True  # Start as if we're in a new paragraph

    for i, line in enumerate(lines):
        line_content = line.strip()

        # Handle empty lines as paragraph breaks
        if not line_content:
            result = _handle_empty_line(
                result,
                current_paragraph,
                indent,
                max_length,
            )
            current_paragraph = []
            in_new_paragraph = True
            continue

        # Process the current line
        prev_line = lines[i - 1] if i > 0 else ""
        result, current_paragraph, in_new_paragraph, first_line_indent = _process_line(
            line=line,
            prev_line=prev_line,
            result=result,
            current_paragraph=current_paragraph,
            in_new_paragraph=in_new_paragraph,
            first_line_indent=first_line_indent,
            indent=indent,
            max_length=max_length,
        )

    # Process any remaining paragraph content
    if current_paragraph:
        paragraph_text = " ".join(current_paragraph)
        wrapped = _wrap_single_line(paragraph_text, indent, max_length)
        result.append(wrapped)

    return result


def _handle_empty_line(
    result: list[str],
    current_paragraph: list[str],
    indent: int,
    max_length: int,
) -> list[str]:
    """Handle an empty line in the description.

    Args:
        result: The current result list
        current_paragraph: The current paragraph being built
        indent: The indentation level
        max_length: The maximum line length

    Returns:
        Updated result list
    """
    if current_paragraph:
        # Join the current paragraph with spaces and add it to the result
        paragraph_text = " ".join(current_paragraph)
        wrapped = _wrap_single_line(paragraph_text, indent, max_length)
        result.append(wrapped)
    result.append(f"{indent * ' '}#")
    return result


def _process_line(  # noqa: PLR0913
    line: str,
    prev_line: str,
    result: list[str],
    current_paragraph: list[str],
    in_new_paragraph: bool,
    first_line_indent: int,
    indent: int,
    max_length: int,
) -> tuple[list[str], list[str], bool, int]:
    """Process a single line of the description.

    Args:
        line: The original line
        prev_line: The previous line
        result: The current result list
        current_paragraph: The current paragraph being built
        in_new_paragraph: Whether we're starting a new paragraph
        first_line_indent: The indentation of the first line in the paragraph
        indent: The indentation level
        max_length: The maximum line length

    Returns:
        Tuple of (result, current_paragraph, in_new_paragraph, first_line_indent)
    """
    line_content = line.strip()
    # Calculate the indentation of this line
    line_indent = len(line) - len(line.lstrip())

    # If we're starting a new paragraph (including first line)
    if in_new_paragraph:
        # Reset the reference indentation for each new paragraph
        first_line_indent = line_indent
        in_new_paragraph = False

    # Calculate relative indentation to the first line of the current paragraph
    relative_indent = max(0, line_indent - first_line_indent)

    # If this line has significant indentation or starts with a marker,
    # treat it as a specially formatted line
    if relative_indent > INDENT or line_content.startswith(("-", "*", "1.", "2.")):
        # First, process any accumulated paragraph
        if current_paragraph:
            paragraph_text = " ".join(current_paragraph)
            wrapped = _wrap_single_line(paragraph_text, indent, max_length)
            result.append(wrapped)
            current_paragraph = []

        # Then handle this formatted line
        result.append(f"{indent * ' '}# {relative_indent * ' '}{line_content}")
    # This is part of a flowing paragraph
    # Check if it's a continuation of the previous line (mid-sentence)
    elif _is_mid_sentence_continuation(prev_line, current_paragraph):
        # This appears to be a mid-sentence line break, add to current paragraph
        current_paragraph.append(line_content)
    else:
        # This seems to be a new paragraph or continuation
        if current_paragraph:
            paragraph_text = " ".join(current_paragraph)
            wrapped = _wrap_single_line(paragraph_text, indent, max_length)
            result.append(wrapped)
            current_paragraph = []

        # Start a new paragraph
        current_paragraph.append(line_content)

    return result, current_paragraph, in_new_paragraph, first_line_indent


def _is_mid_sentence_continuation(
    prev_line: str,
    current_paragraph: list[str],
) -> bool:
    """Check if the current line is a continuation of the previous line.

    Args:
        prev_line: The previous line
        current_paragraph: The current paragraph being built

    Returns:
        True if the line is a mid-sentence continuation
    """
    return bool(
        prev_line.strip()
        and not prev_line.strip().endswith((".", ":", "?", "!"))
        and not current_paragraph,
    )


def wrap_description(
    description: str,
    indent: int,
    max_length: int = 78,
) -> str | list[str]:
    """Wrap a description to fit within a maximum length.

    If the description contains embedded line returns, returns a list of strings.
    Otherwise, returns a single string.
    """
    if not description:
        return ""

    # Check if the description contains embedded line returns
    if "\n" in description:
        return _process_multiline_description(description, indent, max_length)

    return _wrap_single_line(description, indent, max_length)


def path_to_str(data: dict | list | Path | Any) -> dict | list | str | Any:
    """Convert any Path objects to strings recursively."""
    if isinstance(data, Path):
        return str(data)
    elif isinstance(data, dict):
        return {k: path_to_str(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [path_to_str(item) for item in data]
    return data


def _format_env_vars(
    env_vars: list[str],
    indent: int,
    max_length: int = 78,
) -> list[str]:
    """Format environment variables, handling cases where they would exceed line length.

    Args:
        env_vars: List of environment variable names
        indent: The indentation level
        max_length: The maximum line length

    Returns:
        List of formatted strings with environment variables
    """
    if not env_vars:
        return []

    # Calculate the available space after indent and prefix
    prefix = f"{indent * ' '}# Environment variables: "
    available_space = max_length - len(prefix)

    # Try to fit all env vars on one line
    single_line = ", ".join(env_vars)
    if len(single_line) <= available_space:
        return [f"{prefix}{single_line}"]

    # If they don't fit, format as a list
    result = [f"{indent * ' '}# Environment variables:"]
    for env_var in env_vars:
        result.append(f"{indent * ' '}#   - {env_var}")

    return result


def _process_class_docstring(
    class_docstring: str | None,
    section_key: str,
    line: str,
) -> list[str] | None:
    """Process a class-level docstring if the current line defines a class.

    Args:
        class_docstring: The class docstring to process
        section_key: The section key for the class
        line: The current line being processed

    Returns:
        List of wrapped docstring lines if applicable, None otherwise
    """
    if class_docstring is None:
        return None

    # Check if this line defines a class and is not indented
    is_comment = line.strip().startswith("#")
    is_indented = line.startswith(" ")
    is_key = ":" in line
    key_name = line.split(":", 1)[0].strip()

    if is_key and not is_comment and not is_indented and key_name in section_key:
        # Process the class-level docstring
        wrapped_docstring = _process_multiline_description(
            class_docstring,
            0,
            78,
        )
        if isinstance(wrapped_docstring, str):
            return [wrapped_docstring]
        return wrapped_docstring

    return None


def _process_field_comments(
    line: str,
    section_value: dict,
    field_descriptions: dict,
    config_class,
) -> list[str]:
    """Process field descriptions and environment variables.

    Args:
        line: The current line being processed
        section_value: The section value dictionary
        field_descriptions: Dictionary mapping field names to descriptions
        config_class: The configuration class, if available

    Returns:
        List of comment lines for the field
    """
    result = []

    # Check if this line defines a field (has a colon)
    is_comment = line.strip().startswith("#")
    is_indented = line.startswith(" ")
    is_key = ":" in line
    key_name = line.split(":", 1)[0].strip()

    if not (is_key and not is_comment and is_indented and key_name in section_value):
        return result

    # Extract field information
    indent = len(line) - len(line.lstrip())
    description = field_descriptions.get(key_name)
    env_vars = []

    if config_class is not None:
        env_vars = config_class.get_field_env_vars(key_name)

    # Add description as a comment if available
    if description:
        # Process field descriptions
        wrapped_description = _process_multiline_description(
            description,
            indent,
            78,
        )
        if isinstance(wrapped_description, list):
            result.extend(wrapped_description)
        else:
            result.append(wrapped_description)

    # Add environment variables if available
    if env_vars:
        env_var_lines = _format_env_vars(env_vars, indent, 78)
        result.extend(env_var_lines)

    return result


def generate_yaml_with_comments(config: dict, manager: "ConfigurationManager") -> str:
    """Generate YAML string with field descriptions as comments.

    Args:
        config: The configuration dictionary
        manager: The configuration manager instance

    Returns:
        YAML string with comments
    """
    output_lines = []

    # Process each section of the configuration
    for section_key, section_value in config.items():
        # Get the configuration class for this section if available
        config_class = manager.config_classes.get(section_key)
        class_docstring = config_class.__doc__ if config_class else None
        field_descriptions = {}
        if config_class is not None:
            field_descriptions = config_class.get_field_descriptions()

        # Process fields before dumping to YAML to remove any embedded descriptions
        section_to_dump = {section_key: {}}
        for field_name, field_value in section_value.items():
            section_to_dump[section_key][field_name] = field_value

        # Convert the section to YAML
        section_yaml = yaml.dump(
            section_to_dump,
            default_flow_style=False,
            sort_keys=False,
        )

        # Process the YAML line by line to add comments
        lines = section_yaml.split("\n")
        for line in lines:
            # Skip empty lines
            if not line.strip():
                output_lines.append(line)
                continue

            # Process class docstring if applicable
            class_comments = _process_class_docstring(
                class_docstring,
                section_key,
                line,
            )
            if class_comments:
                output_lines.extend(class_comments)

            # Process field comments if applicable
            field_comments = _process_field_comments(
                line,
                section_value,
                field_descriptions,
                config_class,
            )
            if field_comments:
                output_lines.extend(field_comments)

            # Add the original line
            output_lines.append(line)

    return "\n".join(output_lines)
