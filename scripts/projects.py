"""This script contains functions that check and return information
about the projects in the repository."""

import os
import sys
from pathlib import Path
from typing import Any

import click
import yaml

# Workspace root is the parent directory of the scripts directory
WORKSPACE_ROOT = Path(__file__).parent.parent


def find_projects() -> list[dict[str, Any]]:
    """Find all projects in the workspace with versionbump.yaml files.

    Returns:
        A list of dictionaries containing project information:
        - name: Project name from versionbump.yaml
        - title: Project title from versionbump.yaml
        - description: Project description from versionbump.yaml
        - path: Path to the project directory, relative to workspace root
        - version: Current version from versionbump.yaml
    """
    projects = []

    for root, _, files in os.walk(WORKSPACE_ROOT):
        if "versionbump.yaml" in files:
            project_dir = Path(root)
            relative_path = project_dir.relative_to(WORKSPACE_ROOT)

            try:
                with open(project_dir / "versionbump.yaml") as f:
                    config = yaml.safe_load(f)

                # Extract the relevant information
                project_info = {
                    "name": config.get("name", ""),
                    "title": config.get("title", ""),
                    "description": config.get(
                        "descripton", ""
                    ),  # Note: "descripton" is misspelled in the example
                    "path": str(relative_path),
                    "version": config.get("version", ""),
                }
                projects.append(project_info)
            except Exception as e:
                print(
                    f"Error reading versionbump.yaml in {relative_path}: {e}",
                    file=sys.stderr,
                )

    return projects


@click.group()
def cli() -> None:
    """Project management commands."""
    pass


@cli.command(name="list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def list_projects(output_format: str) -> None:
    """List all projects in the workspace."""
    projects = find_projects()

    if output_format == "json":
        import json

        print(json.dumps(projects, indent=2))
    else:
        for project in projects:
            print(f"Name: {project['name']}")
            print(f"Title: {project['title']}")
            print(f"Description: {project['description']}")
            print(f"Path: {project['path']}")
            print(f"Version: {project['version']}")
            print()


@cli.command(name="get")
@click.option("--name", help="Project name to search for")
@click.option("--path", help="Project path to search for")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
def get_project(name: str | None, path: str | None, output_format: str) -> None:
    """Get information about a specific project."""
    if not name and not path:
        print("Error: Either --name or --path must be specified", file=sys.stderr)
        sys.exit(1)

    projects = find_projects()

    # Find the project by name or path
    project = None
    if name:
        project = next((p for p in projects if p["name"] == name), None)
    elif path:
        # Normalize path by removing leading/trailing slashes
        normalized_path = path.strip("/")
        project = next((p for p in projects if p["path"] == normalized_path), None)

    if not project:
        print(f"Error: Project not found: {name or path}", file=sys.stderr)
        sys.exit(1)

    if output_format == "json":
        import json

        print(json.dumps(project, indent=2))
    else:
        print(f"Name: {project['name']}")
        print(f"Title: {project['title']}")
        print(f"Description: {project['description']}")
        print(f"Path: {project['path']}")
        print(f"Version: {project['version']}")


@cli.command(name="paths")
def list_paths() -> None:
    """List just the paths of all projects.

    Useful for scripting, outputs one path per line.
    """
    projects = find_projects()
    for project in projects:
        print(project["path"])


if __name__ == "__main__":
    cli()
