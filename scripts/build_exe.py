import os
import re
from pathlib import Path

import click
from sema4ai.build_common.root_dir import get_root_dir
from sema4ai.build_common.workflows import (
    build_and_sign_executable,
    is_in_github_actions,
)

repo_root_dir = Path(os.path.normpath(os.path.abspath(__file__))).parent.parent
server_dir = repo_root_dir / "server"
assert os.path.exists(server_dir), f"Server directory not found at {server_dir}"


def get_pyproject_version() -> str:
    pyproject_path = server_dir / "pyproject.toml"

    if not pyproject_path.exists():
        raise ValueError(f"pyproject.toml not found at {pyproject_path}")

    import tomllib

    with open(pyproject_path, "rb") as f:
        toml_data = tomllib.load(f)

    version = toml_data["project"]["version"]
    if not version:
        raise ValueError(
            "Can't detect version for building executable from "
            f"pyproject.toml ({pyproject_path})"
        )
    return version


@click.group()
def app():
    """Build and manage project executable."""
    pass


@app.command()
@click.option("--debug", is_flag=True, help="Build in debug mode")
@click.option(
    "--ci",
    type=bool,
    is_flag=True,
    default=False,
    help="Build in CI mode, disabling interactive prompts",
)
@click.option(
    "--dist-path", type=click.Path(), default="dist", help="Path to the dist directory"
)
@click.option(
    "--sign", is_flag=True, help="Sign the executable", default=is_in_github_actions()
)
@click.option(
    "--go-wrapper", is_flag=True, help="Build the Go wrapper too", default=False
)
@click.option(
    "--version",
    type=str,
    help="Version of the executable (gotten from server/pyproject.toml if not passed)",
)
def build_executable(  # noqa: PLR0913
    debug: bool,
    ci: bool,
    dist_path: str,
    sign: bool,
    go_wrapper: bool,
    version: str | None = None,
) -> None:
    """Build the server project executable via PyInstaller."""
    import shutil
    import sys

    os.chdir(server_dir)

    if is_in_github_actions():
        if version:
            raise ValueError(
                "'--version' flag can't be used when running in Github Actions"
            )
        version = get_pyproject_version()

    elif not version:
        version = get_pyproject_version()
        version += "-local"

    elif len(version) < 1 or not re.match(r".*-local$", version):
        raise ValueError("Version must be non-empty and end with '-local'")

    print(f"Building executable with version: {version}")

    build_and_sign_executable(
        root_dir=get_root_dir(),
        name="agent-server",
        debug=debug,
        ci=ci,
        dist_path=Path(dist_path),
        sign=sign,
        go_wrapper=go_wrapper,
        version=version,
    )

    # to check if signed:  spctl -a -vvv -t install /server/dist/final/agent-server

    if go_wrapper:
        # Now, copy from server/dist/final/agent-server to dist/agent-server
        # (.exe if windows)
        final_exe_path = server_dir / dist_path / "final" / "agent-server"
        dest_exe_path = repo_root_dir / dist_path / "agent-server"

        is_windows = sys.platform == "win32"

        if is_windows:
            final_exe_path = final_exe_path.with_suffix(".exe")
            dest_exe_path = dest_exe_path.with_suffix(".exe")

        os.makedirs(dest_exe_path.parent, exist_ok=True)

        shutil.copy(final_exe_path, dest_exe_path)
        print(f"agent-server executable at: {dest_exe_path}")


@app.command()
def clean():
    """Clean server build artifacts."""
    from sema4ai.build_common.workflows import clean_common_build_artifacts

    os.chdir(server_dir)

    clean_common_build_artifacts(get_root_dir())


if __name__ == "__main__":
    app()
