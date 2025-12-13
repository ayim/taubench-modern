from agent_platform.core.errors.base import PlatformHTTPError

VERIFIED_QUERY_NAME_MAX_LENGTH = 50


def is_valid_data_frame_name(name: str) -> bool:
    """Validate a data frame name."""
    import keyword

    if not name.isidentifier() or keyword.iskeyword(name):
        return False
    return True


class DataFrameNameError(PlatformHTTPError):
    """Error raised when a data frame name is not valid."""

    def __init__(self, message: str):
        from agent_platform.core.errors.responses import ErrorCode

        super().__init__(
            error_code=ErrorCode.UNPROCESSABLE_ENTITY,
            message=message,
        )


class VerifiedQueryNameError(PlatformHTTPError):
    """Error raised when a verified query name is not valid."""

    def __init__(self, message: str):
        from agent_platform.core.errors.responses import ErrorCode

        super().__init__(
            error_code=ErrorCode.UNPROCESSABLE_ENTITY,
            message=message,
        )


def data_frame_name_to_verified_query_name(name: str) -> str:
    """Convert a data frame name to a verified query name.

    Converts data frame names (with underscores) to human-readable verified query names.
    Example: 'active_oakland_schools' -> 'Active Oakland Schools'

    Args:
        name: The data frame name to convert.

    Returns:
        A human-readable verified query name with spaces and title case.
    """
    # Replace underscores with spaces and apply title case
    return name.replace("_", " ").title()


def validate_verified_query_name(name: str) -> str:
    """Validate and clean a verified query name.

    Verified query names can be human-readable and contain:
    - Alphanumeric characters (letters and numbers)
    - Spaces (but not leading/trailing)

    Args:
        name: The name to validate.

    Returns:
        The cleaned name (trimmed of leading/trailing whitespace).

    Raises:
        VerifiedQueryNameError: If the name is invalid.
    """
    cleaned = name.strip()

    if not cleaned:
        raise VerifiedQueryNameError("Verified query name cannot be empty.")

    if len(cleaned) > VERIFIED_QUERY_NAME_MAX_LENGTH:
        raise VerifiedQueryNameError(
            f"Verified query name must be {VERIFIED_QUERY_NAME_MAX_LENGTH} characters or less."
        )

    # Check that name contains only alphanumeric characters and spaces
    if not all(c.isalnum() or c.isspace() for c in cleaned):
        raise VerifiedQueryNameError("Verified query name can only contain letters, numbers, and spaces.")

    return cleaned


def make_data_frame_name_valid(name: str) -> str:
    """Make a data frame name valid. Throws a DataFrameNameError if the name is not valid."""
    from sema4ai.common.text import slugify

    valid_name = name
    if not is_valid_data_frame_name(valid_name):
        valid_name = slugify(valid_name).replace("-", "_")
        if not is_valid_data_frame_name(valid_name):
            raise DataFrameNameError(f"Unable to create a valid data frame name from the provided name ({name!r}).")
    return valid_name
