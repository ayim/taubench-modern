from typing import NamedTuple


class StaleThreadsResult(NamedTuple):
    thread_id: str
    file_id: str
    file_path: str | None
