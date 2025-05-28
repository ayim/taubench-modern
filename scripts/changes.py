"""This script assists with the drafting of a changelog through the use
of the towncrier tool.

Generally, the entrypoint for this script will be via the Makefile
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import click
import yaml

# Import from projects.py using a direct file import
# Since the script is imported directly, we need to use sys.path to ensure it's found
# TODO: This hack will be removed when we rework the entire script folder to be
#       a monorepo utility package. ~ @kylie-bee
sys.path.insert(0, str(Path(__file__).parent))
from projects import WORKSPACE_ROOT, find_projects


def _find_project_root(project_name: str | None, print_available: bool = True) -> Path:
    """Find the root directory of a project based on its name.

    Args:
        project_name: The name of the project to find. If None, uses the current
                      directory.
        print_available: Whether to print available projects if the requested
                        project is not found.

    Returns:
        The path to the project root directory.

    Raises:
        ValueError: If the project cannot be found and print_available is False.
    """
    if not project_name:
        return Path.cwd()

    # Use find_projects from projects.py to get all projects
    projects = find_projects()

    # Find the project by name
    for project in projects:
        if project["name"] == project_name:
            return WORKSPACE_ROOT / project["path"]

    if print_available:
        print(f"Error: Project '{project_name}' not found. Available projects:")
        for project in projects:
            if project["name"]:  # Only show projects with names
                print(f"  - {project['name']} ({project['title']})")
        print("\nPlease specify a valid project using --project")
        sys.exit(1)
    else:
        raise ValueError(f"Could not find project '{project_name}'")


def _get_towncrier_config(release: bool = False) -> str:
    """Get the towncrier config to use."""
    return "towncrier-for-release.toml" if release else "towncrier.toml"


def _get_changelog_path(release: bool = False) -> Path:
    """Get the changelog path to use."""
    return Path("CHANGELOG.md") if release else Path("CHANGELOG-PRE-RELEASE.md")


def _run_command(
    cmd: str, hide: bool = False, warn: bool = False, cwd: Path | None = None
) -> subprocess.CompletedProcess | subprocess.CalledProcessError:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd, shell=True, check=not warn, capture_output=True, text=True, cwd=cwd
        )
        if not hide:
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        if warn:
            return e
        raise


@click.group()
def cli():
    """Changelog management commands."""
    pass


def _find_available_projects() -> list[tuple[str, str, Path]]:
    """Find all available projects in the workspace.

    Returns:
        List of tuples containing (package_name, project_name, project_root)
    """
    # Use the find_projects function from projects.py
    projects_info = find_projects()
    result = []

    for project in projects_info:
        if project["name"]:  # Only include projects with names
            project_path = WORKSPACE_ROOT / project["path"]
            result.append((project["name"], project["title"], project_path))

    return sorted(result, key=lambda x: x[0])


def _get_project(project: str | None) -> str | None:
    """Get and validate the project name.

    If no project is specified, presents a numbered list of available projects
    for selection.
    """
    if project:
        return project

    # Find all available projects
    projects = _find_available_projects()

    if not projects:
        print("No projects found in workspace.")
        return None

    print("\nAvailable projects:")
    for i, (package, name, _) in enumerate(projects, 1):
        print(f"{i}. {package} ({name})")
    print(f"{len(projects) + 1}. Use current directory")

    while True:
        try:
            choice = input("\nSelect project (number): ").strip()
            if not choice:
                return None

            choice_num = int(choice)
            if 1 <= choice_num <= len(projects):
                return projects[choice_num - 1][0]  # Return package name
            if choice_num == len(projects) + 1:
                return None
            print("Invalid selection. Please try again.")
        except ValueError:
            print("Please enter a number.")


@cli.command(name="create-change")
@click.option("--kind", help="The kind of news fragment to create")
@click.option("--issue", help="The Linear issue to link to")
@click.option("--section", help="The section of the news fragment to create")
@click.option("--content", help="The content of the news fragment")
@click.option("--project", help="The project to create the change for")
def create_news_fragment(
    kind: str | None = None,
    issue: str | None = None,
    section: str | None = None,
    content: str | None = None,
    project: str | None = None,
) -> None:
    """
    Create a news fragment for the changelog.

    Args:
        kind: The kind of news fragment to create, must be one of:
            - feature: A new feature
            - bugfix: A bug fix
            - doc: A documentation improvement
            - removal: A removal of a feature or API
            - misc: A miscellaneous change
            - hidden: Additional information not pertinent to client users
        issue: The Linear issue to link to. Use "+" to create an orphaned news fragment.
        content: The content of the news fragment, optional.
        section: The section of the news fragment to create, must be one of:
            - "": Core server changes (default)
            - "Public API": Changes to the public API
            - "Private API": Changes to private/internal APIs
        project: The project to create the change for. If not provided, uses the
            current directory.
    """
    # Get validated parameters (with prompts if needed)
    project = _get_project(project)

    # Get project root
    project_root = _find_project_root(project)

    # Get remaining validated parameters
    kind = _get_news_kind(kind)
    issue = _get_news_issue(issue)
    section = _get_news_section(section)
    content = _get_news_content(content)

    # Execute towncrier command
    section_cmd = f'--section "{section}"' if section else ""
    content_cmd = f'--content "{content}"' if content else ""
    file_name = f"{issue}.{kind}.md"

    _run_command(f"towncrier create {section_cmd} {content_cmd} {file_name}", cwd=project_root)


def _get_news_kind(kind: str | None) -> str:
    """Get and validate the news fragment kind."""
    valid_types = ["feature", "bugfix", "doc", "removal", "misc", "hidden"]

    # Interactive prompt for type if not provided
    if not kind:
        print("Available news fragment types:")
        for i, valid_type in enumerate(valid_types, 1):
            print(f"{i}. {valid_type}")

        while True:
            type_input = input(f"Select news fragment type (1-{len(valid_types)} or type name): ")
            if type_input.isdigit() and 1 <= int(type_input) <= len(valid_types):
                kind = valid_types[int(type_input) - 1]
                break
            elif type_input in valid_types:
                kind = type_input
                break
            else:
                print("Invalid selection. Please try again.")

    # Validate type
    if kind not in valid_types:
        raise ValueError(f"Invalid news fragment type. Must be one of: {', '.join(valid_types)}")

    return kind


def _get_news_issue(issue: str | None) -> str:
    """Get and validate the Linear issue."""
    # Interactive prompt for issue if not provided
    if not issue:
        issue = input("Enter the Linear issue to link to: ")
        if not issue:
            raise ValueError("Issue is required")

    # Normalize issue format: convert "gpt-123" to "GPT-123"
    issue = issue.upper()

    # Validate issue format with regex (e.g., GPT-123)
    issue_pattern = re.compile(r"^[A-Z]+-\d+$|^\+$")
    if not issue_pattern.match(issue):
        raise ValueError(
            "Issue must be in the format 'XXX-123' (project code followed "
            "by a number) or '+' for an orphaned news fragment"
        )

    return issue


def _get_news_section(section: str | None) -> str:
    """Get and validate the news fragment section."""
    valid_sections = ["", "Public API", "Private API"]

    # Interactive prompt for section if not provided
    if section is None:
        print("Available sections:")
        for i, valid_section in enumerate(valid_sections, 1):
            section_display = valid_section if valid_section else "(Default - Core server changes)"
            print(f"{i}. {section_display}")

        while True:
            section_input = input(f"Select section (1-{len(valid_sections)} or section name): ")
            if section_input.isdigit() and 1 <= int(section_input) <= len(valid_sections):
                section = valid_sections[int(section_input) - 1]
                break
            elif section_input in valid_sections:
                section = section_input
                break
            elif not section_input:
                section = ""
                break
            else:
                print("Invalid selection. Please try again.")

    # Validate section
    if section not in valid_sections:
        raise ValueError(
            f"Invalid section. Must be one of: "
            f"{', '.join([s if s else '(empty)' for s in valid_sections])}"
        )

    return section


def _get_news_content(content: str | None) -> str:
    """Get the news fragment content."""
    # Interactive prompt for content if not provided
    if not content:
        print("Enter the content of the news fragment (single line only):")
        content = input("> ")

    return content


@cli.command(name="build-changes")
@click.option("--release", is_flag=True, help="Whether to build the changelog for a release")
@click.option(
    "--draft",
    is_flag=True,
    help="Whether to build the changelog as a draft and print to stdout",
)
@click.option(
    "--commit",
    is_flag=True,
    help="Whether to commit the changes. If --commit-message is not provided, "
    "will amend the last commit.",
)
@click.option(
    "--commit-message",
    help="Message to use for the commit. If not provided with --commit, "
    "will amend the last commit.",
)
@click.option(
    "--ci",
    is_flag=True,
    help="Whether to build the changelog in CI mode, disabling interactive prompts",
)
@click.option("--project", help="The project to build changes for")
def build_changelog(  # noqa: PLR0913 we need all the flags to build the changelog
    release: bool = False,
    draft: bool = False,
    commit: bool = False,
    commit_message: str | None = None,
    ci: bool = False,
    project: str | None = None,
) -> None:
    """
    Build the changelog.

    Args:
        release: Whether to build the changelog for a release.
        draft: Whether to build the changelog as a draft and print to stdout.
        commit: Whether to commit the changes.
        commit_message: Message to use for the commit. If not provided with --commit,
            will amend the last commit.
        ci: Whether to build the changelog in CI mode, disabling interactive prompts.
        project: The project to build changes for. If not provided, uses
            the current directory.
    """
    # Get project root
    project_root = _find_project_root(project)

    draft_cmd = "--draft" if draft else ""
    config_to_use = _get_towncrier_config(release)
    # Keep and yes are mutually exclusive.
    keep_cmd = "--keep" if not release else ""
    yes_cmd = "--yes" if ci and release else ""

    if not release:
        # Check if the pre-release changelog file only has a header
        pre_release_path = project_root / _get_changelog_path(False)
        if pre_release_path.exists() and pre_release_path.read_text() == "# Unreleased\n":
            pre_release_path.unlink()

    try:
        _run_command(
            f"towncrier build --config {config_to_use} {draft_cmd} {keep_cmd} {yes_cmd}",
            cwd=project_root,
        )
    except subprocess.CalledProcessError as e:
        print(f"\nError: Failed to build changelog for project '{project or 'current directory'}'")
        print("This could be because:")
        print("  1. No changes have been made since the last release")
        print("  2. The project directory structure is incorrect")
        print("  3. The towncrier configuration is invalid")
        print("\nCommand output:")
        print(e.stdout)
        if e.stderr:
            print("\nError output:")
            print(e.stderr)
        sys.exit(1)

    if draft:
        return

    if release:
        # Clear the pre-release changelog file and write a new header
        pre_release_path = project_root / _get_changelog_path(False)
        pre_release_path.write_text("# Unreleased\n")
    else:
        # Move the new fragments to the pre-release folder for future release log build
        new_base_path = project_root / "changes/new"
        prerelease_base_path = project_root / "changes/prereleased"

        # Find all subdirectories recursively
        for dirpath, _, _ in os.walk(new_base_path):
            # Convert to Path object
            dir_path = Path(dirpath)
            # Get relative path from new_base_path
            rel_path = dir_path.relative_to(new_base_path)
            # Create corresponding path in prereleased
            target_dir = prerelease_base_path / rel_path
            # Ensure target directory exists
            target_dir.mkdir(parents=True, exist_ok=True)

            # Move all markdown files from this directory using git mv
            for fragment in dir_path.glob("*.md"):
                target_file = target_dir / fragment.name
                # Use git mv instead of shutil.move to properly track history
                _run_command(f"git mv {fragment} {target_file}", warn=True, cwd=project_root)

    if commit:
        _commit_changes(commit_message)


def _commit_changes(commit_message: str | None) -> None:
    """Commit changes to the repository.

    Args:
        commit_message: The commit message to use. If None, will amend the last commit.
    """
    if commit_message:
        _run_command(f"git commit -m '{commit_message}'", cwd=WORKSPACE_ROOT)
    else:
        _run_command("git commit --amend --no-edit", cwd=WORKSPACE_ROOT)


@cli.command(name="check-changes")
@click.option("--error-on-missing", is_flag=True, help="Whether to exit on error")
@click.option(
    "--project",
    help="The project to check changes for. Use 'ALL' to check all projects.",
)
def check_changelog(error_on_missing: bool = False, project: str | None = None) -> None:
    """
    Check the changelog.

    Args:
        error_on_missing: Whether to exit on error.
        project: The project to check changes for. If 'ALL', checks all projects.
                If not provided, uses the current directory.
    """
    # Check if we should check all projects
    if project == "ALL":
        projects = _find_available_projects()
        if not projects:
            print("No projects found with towncrier configuration.")
            if error_on_missing:
                sys.exit(1)
            return

        # Track if any project failed
        any_failed = False

        # Check each project
        for package_name, project_name, project_root in projects:
            print(f"\nChecking changes for {project_name} ({package_name})...")
            no_fragments = _check_single_project(project_root)

            if no_fragments:
                print(f"No news fragments found for {project_name}!")
                any_failed = True

        if error_on_missing and any_failed:
            sys.exit(1)
    else:
        # Check a single project
        project_root = _find_project_root(project)
        no_fragments = _check_single_project(project_root)

        if error_on_missing and no_fragments:
            print("No news fragments found!")
            sys.exit(1)


def _check_single_project(project_root: Path) -> bool:
    """
    Check a single project for changelog entries.

    Args:
        project_root: Path to the project root

    Returns:
        bool: True if no fragments were found, False otherwise
    """
    try:
        config_to_use = _get_towncrier_config(release=False)
        # Use absolute path to the config file since we're running from workspace root
        config_path = project_root / config_to_use
        branch_to_use = "origin/development"
        run_result = _run_command(
            f"towncrier check --config {config_path} --compare-with {branch_to_use}",
            hide=True,
            warn=True,
            cwd=WORKSPACE_ROOT,  # Always run from workspace root
        )

        # Print the output
        print(run_result.stdout)

        # Check if no fragments were found
        return "No new newsfragments found on this branch." in run_result.stdout
    except Exception as e:
        print(f"Error checking project: {e!s}")
        return True  # Treat errors as failures


@cli.command(name="create-release-notes")
@click.option("--windows-x64-url", required=True, help="URL to the Windows x64 binary")
@click.option("--macos-x64-url", required=True, help="URL to the macOS x64 binary")
@click.option("--macos-arm64-url", required=True, help="URL to the macOS ARM64 binary")
@click.option("--linux-x64-url", required=True, help="URL to the Linux x64 binary")
@click.option("--release", is_flag=True, help="Whether to use the release changelog")
@click.option("--output-path", help="Path where to save the release notes file")
@click.option("--project", help="The project to create release notes for")
@click.option(
    "--since-date",
    help="Only include changelog entries on or after this date (format: YYYY-MM-DD or 'today')",
)
def create_release_notes(  # noqa: PLR0913 we need all the flags to generate release notes
    windows_x64_url: str,
    macos_x64_url: str,
    macos_arm64_url: str,
    linux_x64_url: str,
    release: bool | None = None,
    output_path: str | None = None,
    project: str | None = None,
    since_date: str | None = None,
) -> str:
    """
    Create a release notes markdown file with binary download URLs.

    This takes the current changelog (either release or pre-release) and adds
    binary download URLs at the top, saving it as a separate file.

    Args:
        windows_x64_url: URL to the Windows x64 binary
        macos_x64_url: URL to the macOS x64 binary
        macos_arm64_url: URL to the macOS ARM64 binary
        linux_x64_url: URL to the Linux x64 binary
        release: Whether to use the release changelog, auto-detected if None
        output_path: Path where to save the release notes file
        project: The project to create release notes for. If not provided,
            uses the current directory.
        since_date: Only include changelog entries on or after this date
            (format: YYYY-MM-DD or 'today')

    Returns:
        Path to the generated release notes file
    """
    # Get project root
    project_root = _find_project_root(project)

    # Auto-detect if this is a release if not specified
    if release is None:
        current_version = _get_version(project_root)
        # In semantic versioning, pre-releases have identifiers like
        # "-alpha", "-beta", "-rc"
        release = "-" not in current_version
        print(f"Detected version: {current_version} ({'release' if release else 'pre-release'})")

    # Determine which changelog to use
    changelog_path = project_root / _get_changelog_path(release)

    # Read the changelog content
    if not changelog_path.exists():
        raise FileNotFoundError(f"Changelog file not found: {changelog_path}")

    changelog_content = changelog_path.read_text()

    # Filter by date if specified
    if since_date:
        try:
            target_date = _parse_date(since_date)
            # Get the towncrier config to determine title format
            towncrier_config_path = project_root / _get_towncrier_config(release)
            changelog_content = _filter_changelog_by_date(
                changelog_content, target_date, towncrier_config_path
            )
            if not changelog_content:
                raise ValueError(f"No changelog entries found on or after {since_date}")
        except ValueError as e:
            if "time data" in str(e):
                raise ValueError(
                    f"Invalid date format: {since_date}. Please use YYYY-MM-DD format or 'today'."
                ) from e
            else:
                raise

    # Find the first header
    header_match = re.search(r"^#\s+.*$", changelog_content, re.MULTILINE)
    if not header_match:
        raise ValueError(f"No header found in changelog: {changelog_path}")

    header_end_pos = header_match.end()

    # Create binary URLs section
    binary_urls_section = f"""

## Binary Downloads

- Windows x64: {windows_x64_url}
- macOS x64: {macos_x64_url}
- macOS ARM64: {macos_arm64_url}
- Linux x64: {linux_x64_url}
"""

    # Insert binary URLs after the first header and remove any duplicate headers
    # First split the content at the first header
    header = changelog_content[:header_end_pos]
    remaining_content = changelog_content[header_end_pos:].lstrip()

    # Combine everything back together
    release_notes_content = f"{header}{binary_urls_section}\n\n{remaining_content}"

    # Determine output path
    if not output_path:
        temp_dir = project_root / "tmp"
        temp_dir.mkdir(exist_ok=True)
        output_path = str(temp_dir / "RELEASE-NOTES.md")

    # Write the release notes file
    Path(output_path).write_text(release_notes_content)

    print(f"Release notes written to: {output_path}")
    return output_path


def _parse_date(date_string: str) -> tuple[int, int, int]:
    """
    Parse a date string in YYYY-MM-DD format or the special value "today".

    Args:
        date_string: Date string in YYYY-MM-DD format or "today"

    Returns:
        Tuple of (year, month, day)
    """
    import datetime

    if date_string.lower() == "today":
        today = datetime.datetime.now()
        return (today.year, today.month, today.day)

    try:
        date_obj = datetime.datetime.strptime(date_string, "%Y-%m-%d")
        return (date_obj.year, date_obj.month, date_obj.day)
    except ValueError as e:
        raise ValueError(
            f"Invalid date format: {date_string}. Please use YYYY-MM-DD format or 'today'."
        ) from e


def _get_towncrier_title_format(config_path: Path) -> str:
    """
    Get the title format from a towncrier config file.

    Args:
        config_path: Path to the towncrier.toml file

    Returns:
        Title format string or the default format if not specified
    """
    # Default format per towncrier docs (for markdown output)
    default_format = "# {name} {version} ({project_date})"

    if not config_path.exists():
        return default_format

    try:
        with open(config_path) as f:
            content = f.read()

        # Look for title_format in the config
        match = re.search(r'title_format\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)

        return default_format
    except Exception:
        # If there's any error reading the config, fall back to default
        return default_format


def _build_date_pattern_from_format(title_format: str) -> str:
    """
    Build a regex pattern to extract date from a towncrier title format.

    Args:
        title_format: The title format from towncrier config

    Returns:
        Regex pattern string that will extract the date
    """
    # Replace format variables with regex patterns
    # The goal is to identify where the {project_date} is in the format

    # First, escape any regex special characters in the format
    escaped_format = re.escape(title_format)

    # Replace the escaped {project_date} with a capturing group for the date
    # Allow for dates with or without parentheses
    pattern = escaped_format.replace(
        re.escape("{project_date}"), r"(?:\()?(\d{4}-\d{2}-\d{2})(?:\))?"
    )

    # Replace other variables with non-capturing groups
    pattern = pattern.replace(re.escape("{name}"), r"[^\n]+?")
    pattern = pattern.replace(re.escape("{version}"), r"[^\n]+?")
    pattern = pattern.replace(re.escape("{project}"), r"[^\n]+?")

    # Create the full pattern to match the heading
    return r"^#+\s+" + pattern


def _filter_changelog_by_date(
    changelog_content: str,
    target_date: tuple[int, int, int],
    towncrier_config_path: Path,
) -> str:
    """
    Filter a changelog to only include entries that are as recent as or
    more recent than the target date.

    Args:
        changelog_content: The full changelog content
        target_date: Tuple of (year, month, day) to filter by
        towncrier_config_path: Path to the towncrier.toml file

    Returns:
        Filtered changelog content
    """
    import datetime

    # Get the title format from towncrier config
    title_format = _get_towncrier_title_format(towncrier_config_path)

    # Build regex pattern based on the title format
    header_pattern_str = _build_date_pattern_from_format(title_format)
    header_date_pattern = re.compile(header_pattern_str, re.MULTILINE)

    # If we couldn't build a pattern from the title format, fall back to
    # a more generic pattern
    if "{project_date}" not in title_format:
        # Fallback pattern that looks for dates in common formats, including
        # those in parentheses
        header_date_pattern = re.compile(
            r"^#+\s+(?:.*?)(?:\()?(\d{4}-\d{2}-\d{2})(?:\))?", re.MULTILINE
        )

    # Add a direct pattern that matches the specific format seen in the changelog
    direct_pattern = re.compile(
        r"^# .*?(?:Changes|Pre-Release).*?\((\d{4}-\d{2}-\d{2})\)", re.MULTILINE
    )

    # Find all section headers with dates
    sections = []
    section_matches = list(header_date_pattern.finditer(changelog_content))

    # If we didn't find matches with the main pattern, try the direct pattern
    if not section_matches:
        section_matches = list(direct_pattern.finditer(changelog_content))

    if not section_matches:
        # If no sections with dates are found, return the original content
        print("Warning: No dated sections found in changelog. Using entire content.")
        return changelog_content

    # Process each section
    for i, match in enumerate(section_matches):
        section_date_str = match.group(1)
        try:
            date_obj = datetime.datetime.strptime(section_date_str, "%Y-%m-%d")
            section_date = (date_obj.year, date_obj.month, date_obj.day)

            # If this section's date is >= target_date
            if section_date >= target_date:
                # Get the section content
                start_pos = match.start()
                end_pos = (
                    section_matches[i + 1].start()
                    if i + 1 < len(section_matches)
                    else len(changelog_content)
                )
                section_content = changelog_content[start_pos:end_pos]
                sections.append(section_content)
        except ValueError:
            # Skip sections with invalid dates
            continue

    # If we found sections matching the date criteria
    if sections:
        return "".join(sections)

    # No sections matched the date criteria
    return ""


def _get_version(project_root: Path | None = None) -> str:
    """Get the version of the project."""
    try:
        result = _run_command("versionbump show-version", hide=True, cwd=project_root)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # read versionbump.yaml directly
        versionbump_path = (project_root or Path.cwd()) / "versionbump.yaml"
        if versionbump_path.exists():
            with open(versionbump_path) as f:
                versionbump_yaml = yaml.safe_load(f)
                return versionbump_yaml["version"]
        else:
            raise ValueError("Versionbump.yaml not found") from e


if __name__ == "__main__":
    cli()
