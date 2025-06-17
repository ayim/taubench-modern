"""Workitems service."""

__version__ = "0.1.0"

from .lifecycle import make_app
from .main import main

__all__ = [
    "main",
    "make_app",
]
