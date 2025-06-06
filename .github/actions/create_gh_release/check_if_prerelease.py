import os
import sys


def is_prerelease(version: str) -> bool:
    """
    Check if the version string indicates a prerelease by looking for a hyphen.

    Args:
        version (str): The version string to check

    Returns:
        bool: True if it's a prerelease, False otherwise
    """
    return "-" in version


if __name__ == "__main__":
    if len(sys.argv) != 2:  # noqa: PLR2004
        print("Error: Please provide a version string as argument")
        sys.exit(1)

    version = sys.argv[1]
    result = is_prerelease(version)

    # Set GitHub Actions output
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"is_prerelease={'true' if result else 'false'}\n")

    # Print status message
    if result:
        print("This is a prerelease.")
    else:
        print("This is not a prerelease.")
