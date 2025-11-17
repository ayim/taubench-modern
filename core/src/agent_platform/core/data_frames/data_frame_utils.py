from agent_platform.core.errors.base import PlatformHTTPError


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


def make_data_frame_name_valid(name: str) -> str:
    """Make a data frame name valid. Throws a DataFrameNameError if the name is not valid."""
    from sema4ai.common.text import slugify

    valid_name = name
    if not is_valid_data_frame_name(valid_name):
        valid_name = slugify(valid_name).replace("-", "_")
        if not is_valid_data_frame_name(valid_name):
            raise DataFrameNameError(
                f"Unable to create a valid data frame name from the provided name ({name!r})."
            )
    return valid_name
