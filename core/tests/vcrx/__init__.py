"""
Public surface for vcrx.

Usage:
    from vcrx import patched_vcr
"""

from core.tests.vcrx.config import CASSETTE_ROOT_DIR
from core.tests.vcrx.context import patched_vcr
from core.tests.vcrx.env import get_vcr_record_mode
from core.tests.vcrx.persisters.zip_archive import ZipArchivePersister
from core.tests.vcrx.shims.httpx_shim import install_httpx_shim

__all__ = [
    "CASSETTE_ROOT_DIR",
    "ZipArchivePersister",
    "get_vcr_record_mode",
    "install_httpx_shim",
    "patched_vcr",
]
