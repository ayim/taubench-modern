import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_agent_server_build():
    """Test that we can build the agent server"""
    import os

    if os.environ.get("GITHUB_ACTIONS") == "true":
        if sys.platform == "darwin":
            assert os.environ.get("MACOS_SIGNING_CERT") is not None
            assert os.environ.get("MACOS_SIGNING_CERT_PASSWORD") is not None
            assert os.environ.get("MACOS_SIGNING_CERT_NAME") is not None

            assert os.environ.get("APPLEID") is not None
            assert os.environ.get("APPLETEAMID") is not None
            assert os.environ.get("APPLEIDPASS") is not None

        elif sys.platform == "win32":
            assert os.environ.get("VAULT_URL") is not None
            assert os.environ.get("CLIENT_ID") is not None
            assert os.environ.get("TENANT_ID") is not None
            assert os.environ.get("CLIENT_SECRET") is not None
            assert os.environ.get("CERTIFICATE_NAME") is not None

    # Find pyproject.toml in parent directory
    server_root_dir = Path(os.path.abspath(__file__)).parent
    while not (server_root_dir / "pyproject.toml").exists():
        if not server_root_dir.parent or server_root_dir.parent == server_root_dir:
            raise FileNotFoundError("pyproject.toml not found")
        server_root_dir = server_root_dir.parent
    repo_root_dir = server_root_dir.parent

    cmdline = (
        "uv run python scripts/build_exe.py build-executable --go-wrapper --ci".split()
    )
    subprocess.check_call(cmdline, cwd=repo_root_dir)

    expected_exe_path = (
        repo_root_dir
        / "dist"
        / ("agent-server" + ("" if sys.platform != "win32" else ".exe"))
    )
    assert expected_exe_path.exists()
    assert expected_exe_path.is_file()

    output = subprocess.check_output([expected_exe_path, "--version"])
    assert output.decode("utf-8").strip().startswith("Sema4.ai Agent Server v")
