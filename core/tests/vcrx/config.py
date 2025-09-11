import os

"""
Configuration knobs.

You can override the cassette root via env var if desired:
    VCRX_CASSETTE_ROOT=/custom/path
"""

CASSETTE_ROOT_DIR: str = os.getenv(
    "VCRX_CASSETTE_ROOT",
    "core/tests/fixtures/vcr_cassettes",
)
