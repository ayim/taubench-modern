from typing import NamedTuple


class StaleThreadsResult(NamedTuple):
    thread_id: str
    file_id: str
    file_path: str | None


type JSONValue = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
