import contextlib
import os
import time
import zipfile
from typing import Any

from vcr.record_mode import RecordMode

from core.tests.vcrx.bedrock.patch import _suppress_vcr_aiohttp_patchers, patch_bedrock
from core.tests.vcrx.config import CASSETTE_ROOT_DIR
from core.tests.vcrx.env import debug, env_bool, get_vcr_record_mode
from core.tests.vcrx.persisters.zip_archive import ZipArchivePersister
from core.tests.vcrx.shims.httpx_shim import install_httpx_shim
from core.tests.vcrx.shims.httpx_stream import patch_httpx_stream
from core.tests.vcrx.shims.requests_shim import install_requests_shim
from core.tests.vcrx.vcr_builder import build_vcr


def _cassette_exists(relative_path: str) -> bool:
    """Check if a cassette exists in a zip archive or on the filesystem."""
    # Check zip archive first
    archive_path, rel_member = ZipArchivePersister._select_archive(
        os.path.join(CASSETTE_ROOT_DIR, relative_path)
    )
    if os.path.exists(archive_path):
        try:
            with zipfile.ZipFile(archive_path, mode="r") as zf:
                if rel_member in zf.namelist():
                    return True
        except zipfile.BadZipFile:
            pass  # Corrupt zip, will fallback to filesystem

    # Fallback to checking filesystem
    return os.path.exists(os.path.join(CASSETTE_ROOT_DIR, relative_path))


def _handle_missing_cassette(cassette_path: str) -> None:
    """Raises or skips the test if a cassette is missing in replay-only mode."""
    msg = (
        f"Missing cassette '{cassette_path}'. To record it, run with "
        f"VCR_RECORD=new_episodes and re-run this test."
    )
    if env_bool("VCR_STRICT", False):
        raise FileNotFoundError(msg)
    try:
        import pytest

        pytest.skip(msg)
    except (ImportError, Exception) as err:
        raise FileNotFoundError(msg) from err


@contextlib.contextmanager
def patched_vcr(cassette_path: str, **use_kwargs: Any):
    """
    Use VCR with our patches, symmetric matchers, and zip persister.

    Example:
        with patched_vcr("platforms/groq/my_test.yaml"):
            ... code that issues httpx/aiohttp requests ...
    """
    our_vcr = build_vcr()
    install_httpx_shim()  # Ensure shim is installed before VCR context is active
    install_requests_shim()

    t_enter = time.monotonic()
    debug(f"[VCR] Using cassette: {cassette_path} (mode={get_vcr_record_mode()})")

    if get_vcr_record_mode() == RecordMode.NONE and not _cassette_exists(cassette_path):
        _handle_missing_cassette(cassette_path)
        # Yield to prevent further execution if pytest.skip was called
        yield
        return

    use_kwargs.setdefault("allow_playback_repeats", True)
    is_bedrock = str(cassette_path).startswith("platforms/bedrock/")

    # Use ExitStack to flatten nested context managers for better readability
    with contextlib.ExitStack() as stack:
        # For Bedrock, suppress VCR's default aiohttp patchers.
        if is_bedrock:
            stack.enter_context(_suppress_vcr_aiohttp_patchers())

        cassette = stack.enter_context(our_vcr.use_cassette(cassette_path, **use_kwargs))

        # Enter our custom patchers for httpx and Bedrock.
        stack.enter_context(patch_httpx_stream(cassette))
        stack.enter_context(patch_bedrock(cassette_path, cassette))

        debug(f"[VCR] Entered cassette in {time.monotonic() - t_enter:.4f}s")
        yield
        # On exit, ExitStack unwinds everything: patches are restored and cassettes are saved.
