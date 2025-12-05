import re
import sys
from pathlib import Path

from invoke import task

ROOT = Path(__file__).absolute().parent
PACKAGE_NAME = "sema4ai_docint"
TAG_PREFIX = "sema4ai-docint"
TARGETS = ["sema4ai_docint", "tests"]
RUFF_ARGS = "--config pyproject.toml"


def run(c, *cmd, env=None, cwd=None, **options):
    """Helper to run commands with proper options."""
    options.setdefault("echo", True)

    if cwd is None:
        cwd = ROOT

    if env is not None:
        options["env"] = env

    # Handle TARGETS list specially
    if cmd and isinstance(cmd[0], list):
        # If first argument is a list (like TARGETS), expand it
        expanded_cmd = []
        for arg in cmd:
            if isinstance(arg, list):
                expanded_cmd.extend(arg)
            else:
                expanded_cmd.append(arg)
        args = " ".join(expanded_cmd)
    else:
        args = " ".join(cmd)

    # Change to the specified directory before running the command
    if cwd != ROOT:
        args = f"cd {cwd} && {args}"

    return c.run(args, **options)


def to_identifier(value: str) -> str:
    """Convert string to valid Python identifier."""
    value = re.sub(r"[^\w\s_]", "", value.lower())
    value = re.sub(r"[_\s]+", "_", value).strip("_")
    return value


@task
def install(c, update=False, verbose=False):
    """
    Install dependencies using UV.
    Args:
        update: If True, update lock file (CVE updates)
        verbose: Whether to run in verbose mode
    """
    if update:
        print("🔄 Updating lock file...")
        run(c, "uv lock --upgrade")
    print("📦 Installing dependencies...")
    cmd = "uv sync"
    if verbose:
        cmd += " --verbose"
    run(c, cmd)


@task
def devinstall(c, verbose=False):
    """
    Install the package in develop mode and its dependencies.
    Args:
        verbose: Whether to run in verbose mode
    """
    print("📦 Installing in development mode...")
    cmd = "uv sync --group dev"
    if verbose:
        cmd += " --verbose"
    run(c, cmd)


@task
def build(c):
    """Build distributable .tar.gz and .wheel files using UV."""
    print("🔨 Building project...")
    run(c, "uv build")


@task
def test(c, test=None):
    """
    Run unittests using UV.
    Args:
        test: Specific test to run
    """
    cmd = "uv run pytest -rfE -vv"
    if test:
        cmd += f" {test}"
    else:
        cmd += " -n auto"  # Run in parallel
    print(f"🧪 Running tests: {cmd}")
    run(c, cmd)


@task
def lint(c, strict=False):
    """
    Run static analysis and formatting checks.
    Currently runs:
        - Ruff basic checks, then formatting checks
        - isort for sorting imports
        - Optionally Pylint if enabled through strict switch
        - Markdown lint if available

    Args:
        strict: Whether to enable Pylint as well
    """
    print("🔍 Running linter...")
    run(c, "uv run ruff check", *TARGETS)
    run(c, f"uv run ruff format --check {RUFF_ARGS}", *TARGETS)

    if strict:
        run(c, "uv run pylint --rcfile .pylintrc sema4ai_docint")


@task
def typecheck(c, strict=False):
    """
    Type check code using mypy.

    Args:
        strict: Whether to run in strict mode
    """
    print("🔍 Running type checker...")
    cmd = [
        "uv run mypy",
        "--follow-imports=silent",
        "--show-column-numbers",
        "--namespace-packages",
        "--explicit-package-bases",
    ]
    cmd.extend(["sema4ai_docint", "tests"])

    if strict:
        cmd.append("--strict")

    run(c, " ".join(cmd))


@task
def pretty(c):
    """Auto-format code and sort imports."""
    print("📝 Formatting code...")
    run(c, "uv run ruff check --fix", *TARGETS)
    run(c, f"uv run ruff format {RUFF_ARGS}", *TARGETS)


@task
def set_version(c, version):
    """
    Sets a new version for the project in all needed files.

    Args:
        version: New version number (e.g., '1.2.3')
    """
    valid_version_pattern = re.compile(r"^\d+\.\d+\.\d+$")
    if not valid_version_pattern.match(version):
        print(f"❌ Invalid version: {version}. Must be in format major.minor.hotfix")
        return

    version_patterns = (
        re.compile(r"(version\s*=\s*)\"\d+\.\d+\.\d+"),
        re.compile(r"(__version__\s*=\s*)\"\d+\.\d+\.\d+"),
        re.compile(r"(\"version\"\s*:\s*)\"\d+\.\d+\.\d+"),
    )

    def update_version(version, filepath):
        if not Path(filepath).exists():
            return
        with open(filepath, encoding="utf-8") as stream:
            before = stream.read()

        after = before
        for pattern in version_patterns:
            after = re.sub(pattern, rf'\1"{version}', after)

        if before != after:
            print(f"Changed: {filepath}")
            with open(filepath, "w", encoding="utf-8") as stream:
                stream.write(after)

    # Update version in pyproject.toml
    update_version(version, "pyproject.toml")

    # Update version in __init__.py
    init_file = ROOT / "sema4ai_docint" / "__init__.py"
    update_version(version, init_file)

    # Update changelog if it exists
    changelog_file = ROOT / "docs" / "CHANGELOG.md"
    if changelog_file.exists():
        update_changelog_file(changelog_file, version)

    print(f"✅ Updated version to {version}")


def update_changelog_file(file: Path, version: str):
    """Update the changelog file with the new version and changes."""
    from datetime import datetime

    with open(file, "r+", encoding="utf-8") as stream:
        content = stream.read()

        new_version = f"## {version} - {datetime.today().strftime('%Y-%m-%d')}"
        changelog_start_match = re.search(r"# Changelog", content)
        if not changelog_start_match:
            print(f"Did not find # Changelog in: {file}")
            return

        changelog_start = changelog_start_match.end()
        unreleased_match = re.search(r"## Unreleased", content, flags=re.IGNORECASE)
        double_newline = "\n\n"

        new_content = content[:changelog_start] + double_newline + "## Unreleased"
        if unreleased_match:
            released_content = content.replace(unreleased_match.group(), new_version)
            new_content += released_content[changelog_start:]
        else:
            new_content += double_newline + new_version + content[changelog_start:]

        stream.seek(0)
        stream.write(new_content)
        print(f"Changed: {file}")


@task
def docs(c, check=False):
    """
    Build API documentation.
    Args:
        check: Whether to check for document changes
    """
    output_path = ROOT / "docs" / "api"
    if not output_path.exists():
        print("Docs output path does not exist. Skipping...")
        return

    for path in output_path.iterdir():
        path.unlink()

    cmd = ["uv run pdoc", "--output-dir", str(output_path)]
    template_dir = ROOT / "docs" / "templates"
    if template_dir.exists():
        cmd.extend(["--template-dir", str(template_dir)])
    cmd.append(PACKAGE_NAME)

    run(c, " ".join(cmd))

    if check:
        if check_document_changes(c):
            output = run(c, "git --no-pager diff -- docs/api", hide=True)
            raise RuntimeError(f"There are uncommitted docs changes. Changes: {output.stdout}")


def check_document_changes(c):
    """Check if there were new document changes generated by lazydocs."""
    changed_files = (
        run(c, "git --no-pager diff --name-only -- docs/api", hide=True).stdout.strip().splitlines()
    )
    return bool(changed_files)


@task(lint, typecheck, test)
def check_all(c):
    """Run all checks (lint, typecheck, test, docs)."""
    print("🔍 Running all checks...")
    run(c, "inv docs --check")


@task
def make_release(c):
    """Create a release tag."""
    result = run(c, "git rev-parse --abbrev-ref HEAD", hide=True)
    current_branch = result.stdout.strip()

    # Get the default branch name
    try:
        result = run(c, "git symbolic-ref refs/remotes/origin/HEAD", hide=True)
        default_branch = result.stdout.strip().replace("refs/remotes/origin/", "")
    except Exception:
        # Fallback to common default branch names
        default_branch = "main"

    if current_branch != default_branch:
        print(f"❌ Not on default branch ({default_branch}): {current_branch}")
        sys.exit(1)

    # Get current version from pyproject.toml
    pyproject_content = (ROOT / "pyproject.toml").read_text()
    version_match = re.search(r'version = "([^"]+)"', pyproject_content)
    if not version_match:
        print("❌ Could not find version in pyproject.toml")
        sys.exit(1)
    current_version = version_match.group(1)
    # Get previous tag
    try:
        result = run(c, f"git describe --tags --abbrev=0 --match {TAG_PREFIX}-[0-9]*", hide=True)
        previous_tag = result.stdout.strip()
        previous_version = previous_tag.split("-")[-1]
    except Exception:
        previous_version = None

    if previous_version and previous_version != "beta":
        try:
            import semver

            if semver.compare(current_version, previous_version) <= 0:
                print(
                    f"❌ Current version older/same than previous: "
                    f"{current_version} <= {previous_version}"
                )
                sys.exit(1)
        except ImportError:
            print("⚠️  semver not available, skipping version comparison")

    current_tag = f"{TAG_PREFIX}-{current_version}"
    run(c, "git tag", "-a", current_tag, "-m", f'"Release {current_version} for {PACKAGE_NAME}"')

    print(f"🏷️  Pushing tag: {current_tag}")
    run(c, f"git push origin {current_tag}")


@task
def clean(c):
    """Clean build artifacts."""
    print("🧹 Cleaning build artifacts...")
    # Remove build directories
    for dir_name in ["build", "dist", "__pycache__", ".pytest_cache"]:
        dir_path = ROOT / dir_name
        if dir_path.exists():
            if sys.platform == "win32":
                run(c, f"rmdir /s /q {dir_path}")
            else:
                run(c, f"rm -rf {dir_path}")
    # Remove .pyc files
    if sys.platform == "win32":
        run(c, "for /r . %i in (*.pyc) do @del %i")
    else:
        run(c, "find . -name '*.pyc' -delete")


@task
def publish(c, token):
    """
    Publish to PyPI.
    Args:
        token: PyPI token for authentication
    """
    print("📦 Publishing to PyPI...")
    run(c, f"uv run twine upload --username __token__ --password {token} dist/*")
