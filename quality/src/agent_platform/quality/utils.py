from urllib.parse import urlparse, urlunparse


def safe_join_url(url: str, new_path: str) -> str:
    parsed = urlparse(url)
    new_path = parsed.path.rstrip("/") + new_path
    updated = parsed._replace(path=new_path)
    return urlunparse(updated)
