def fetch_url_data(url: str, timeout: int = 30) -> bytes:
    """Download the resource at `url` and return its raw bytes.

    Args:
        url: The URL to fetch data from
        timeout: Request timeout in seconds

    Returns:
        bytes: The raw content from the URL
    """
    from requests import get

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
    resp = get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.content
