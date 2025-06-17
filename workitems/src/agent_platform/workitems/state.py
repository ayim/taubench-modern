import asyncio

from fastapi import Request

from .db import DatabaseManager


class WorkItemsState:
    def __init__(self, db_manager: DatabaseManager, worker: asyncio.Task):
        self.db_manager = db_manager
        self.worker = worker


def get_state(request: Request) -> WorkItemsState:
    """
    Get the workitems state from the given request.
    """
    return request.app.state.workitems
