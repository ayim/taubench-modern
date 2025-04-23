import os
import re
import sys


def format_version(version: str) -> str:
    """
    Format and validate the version string.

    Args:
        version (str): The version string to format

    Returns:
        str: Formatted version string

    Raises:
        ValueError: If the version string format is invalid
    """
    # Semver pattern from semver/semver#232 by DavidFichtmueller
    # This pattern has been extensively tested against the semver spec
    semver_pattern = (
        r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
        r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
        r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
    )

    # If version doesn't start with 'v' and matches semver pattern, add 'v'
    if not version.startswith("v") and re.match(semver_pattern, version):
        version = f"v{version}"

    # Validate that version starts with exactly one 'v' followed by semver
    v_semver_pattern = f"^v{semver_pattern[1:]}"
    if not re.match(v_semver_pattern, version):
        raise ValueError(f"Invalid version format: {version}")

    return version


if __name__ == "__main__":
    if len(sys.argv) != 2:  # noqa: PLR2004
        print("Error: Please provide a version string as argument")
        sys.exit(1)

    try:
        version = format_version(sys.argv[1])
        # Set GitHub Actions output
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"release_version={version}\n")
        print(f"Formatted version: {version}")
    except ValueError as e:
        print(str(e))
        sys.exit(1)
