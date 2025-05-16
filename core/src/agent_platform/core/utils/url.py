def safe_urljoin(base_url: str, *path_segments: str) -> str:
    """
    Joins one or more relative paths to a base URL,
    preserving all existing path segments
    and avoiding unintended replacement of the last path part.

    Args:
        base_url (str): The base URL.
        *path_segments (str): One or more path components to append.

    Returns:
        str: A new URL with all segments joined properly.
    """
    from urllib.parse import urljoin

    normalized_segments = [
        segment.strip("/") for segment in path_segments if segment.strip("/")
    ]

    if not normalized_segments:
        return base_url

    # Ensure base ends with exactly one slash to avoid replacement behavior
    # If the base_url does not end in a slash, urljoin treats the last segment as a file
    # and replaces it with the new path segment
    cleaned_base = base_url.rstrip("/") + "/"

    relative_path = "/".join(normalized_segments)

    return urljoin(cleaned_base, relative_path)
