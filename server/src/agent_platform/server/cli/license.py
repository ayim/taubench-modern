"""Handle license related CLI arguments."""

import sys

import structlog

from server.constants import ROOT

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def print_license(should_exit: bool = True) -> None:
    """Handle the license argument."""
    license_path = ROOT / "LICENSE"
    try:
        with open(license_path) as f:
            print(f.read())
        if should_exit:
            sys.exit(0)
    except FileNotFoundError:
        print(
            "License file not found. Please visit https://sema4.ai "
            "for license information.",
        )
        if should_exit:
            sys.exit(1)
