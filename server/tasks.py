"""Local invoke tasks for the Agent Server project."""

import os
import platform
import re
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv
from invoke import Context, Failure, task

is_windows = platform.system() == "Windows"


class AnsiStripStream:
    ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

    def __init__(self, fileobj):
        self.fileobj = fileobj

    def write(self, data: str):
        # data is a string, so we remove ANSI codes as strings
        filtered = self.ansi_escape.sub("", data)
        return self.fileobj.write(filtered)

    def flush(self):
        return self.fileobj.flush()


class MultiStream:
    def __init__(self, streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def _build_python_dist(ctx: Context, ci: bool = False) -> None:
    """Builds wheels via Poetry."""
    ctx.run(f"poetry build{' -q' if ci else ''}")


def _set_lib_path(ctx: Context) -> None:
    """
    Sets the library path for PyInstaller if we are in a brew, pyenv, or
    GitHub Actions environment.
    """

    if is_windows:
        # Windows does not use LD_LIBRARY_PATH
        return None
    lib_paths = []

    if os.getenv("GITHUB_ACTIONS"):
        # GitHub Actions environment
        python_path = ctx.run(
            'python -c "import sys; print(sys.prefix)"', hide=True
        ).stdout.strip()
        lib_paths.append(f"{python_path}/lib")
    else:
        try:
            brew_prefix = ctx.run("brew --prefix", hide=True).stdout.strip()
        except Failure:
            brew_prefix = ""

        try:
            current_virtual_env = ctx.run(
                "poetry env info --path", hide=True
            ).stdout.strip()
        except Failure:
            current_virtual_env = ""

        is_pyenv = bool(re.search(r"pyenv.*envs", current_virtual_env))

        if brew_prefix:
            lib_paths.append(f"{brew_prefix}/lib")
        if is_pyenv:
            pyenv_prefix = ctx.run("pyenv virtualenv-prefix", hide=True).stdout.strip()
            lib_paths.append(f"{pyenv_prefix}/lib")

    if lib_paths:
        ld_library_path = ":".join(lib_paths)
        # Invoke passes current environ to all run method calls.
        os.environ["LD_LIBRARY_PATH"] = ld_library_path


def _build_executable(
    ctx: Context,
    debug: bool = False,
    ci: bool = False,
    onefile: bool = False,
    name: str = "agent-server",
    dist_path: str = "dist",
) -> None:
    """Builds the executable via PyInstaller."""
    _set_lib_path(ctx)
    # ctx.run("pyinstaller agent-server-other.spec")
    # return
    args = ["pyinstaller"]
    spec_args = []
    if debug:
        ci = False
        spec_args.append("--debug")
        args.append("--log-level=DEBUG")
    if ci:
        args.append("-y")
    if onefile:
        spec_args.append("--onefile")
    args.append(f"--distpath={dist_path}")
    spec_args.append(f"--name={name}")
    # Must be last arg before any spec_args
    args.append("agent-server.spec")
    if spec_args:
        args.append("--")
        args.extend(spec_args)
    build_log_path = Path("build/build_output.log")
    build_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(build_log_path, "w") as f:
        filtered_f = AnsiStripStream(f)
        split_f = MultiStream([filtered_f, sys.stdout])
        ctx.run(
            " ".join(args),
            out_stream=split_f,
            err_stream=split_f,
            # pty=not is_windows,
            echo=True,
        )


@task
def clean(ctx):
    shutil.rmtree("dist", ignore_errors=True)
    shutil.rmtree("build", ignore_errors=True)


@task
def build(
    ctx: Context,
    wheels: bool = True,
    executable: bool = True,
    debug: bool = False,
    ci: bool = False,
    onefile: bool = False,
    name: str = "agent-server",
    dist_path: str = "dist",
) -> None:
    """
    Build the project. By default, this will build wheels via Poetry and
    an executable via PyInstaller.

    Flags:
        --no-wheels: Skip building wheels.
        --no-executable: Skip building the executable.
        --debug: Build the executable in debug mode, sets --no-ci.
        --ci: Build in CI mode, disabling interactive prompts.
        --onefile: Build the executable as a single file.
        --name: Name of the executable. Defaults to 'agent-server'.
        --dist-path: Path to the dist directory. Defaults to 'dist'.
    """
    if wheels:
        _build_python_dist(ctx, ci)
    if executable:
        _build_executable(
            ctx, debug=debug, ci=ci, onefile=onefile, name=name, dist_path=dist_path
        )


@task(name="server")
def run_server(
    ctx: Context,
    onefile: bool = False,
    exe_path: str = "./dist/agent-server/agent-server",
    env_path: str = "./.env",
    output_path: str = "run.log",
    hide_output: bool = False,
) -> None:
    """
    Run the bundled executable with environment variables from a .env file.

    Args:
        --onefile: Whether the executable was built as a single file, exclusive
          with --exe-path. This sets the executable path to the dist/agent-server
          directory (the default for build --onefile).
        --exe-path: Path to the executable. Cannot be used with --onefile. Defaults
          to the dist/agent-server/agent-server path (the default for build).
        --env-path: Path to the .env file.
        --output-path: Path to the output log file.
        --hide-output: Whether to hide output from the terminal.
    """
    load_dotenv(dotenv_path=env_path)
    if onefile:
        exe_path = Path("./dist/agent-server")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            filtered_f = AnsiStripStream(f)
            ctx.run(
                str(exe_path),
                err_stream=filtered_f,
                out_stream=filtered_f,
                hide=hide_output,
                pty=not is_windows,
            )
    except KeyboardInterrupt:
        pass
