"""Utility to dynamically inject SDMs into agent packages."""

import os
import shutil
import tempfile
import zipfile
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger(__name__)


def inject_sdms_into_agent_package(
    agent_zip_path: Path,
    sdm_source_dirs: list[Path],
) -> Path:
    """
    Inject SDMs from source directories into an agent package zip.

    Creates a temporary modified agent package with SDMs added to the
    semantic_data_models directory and registered in agent-spec.yaml.

    Args:
        agent_zip_path: Path to the original agent zip file
        sdm_source_dirs: List of SDM directories to inject
            (e.g., quality/test-data/sdms/bird_*)

    Returns:
        Path to the modified agent zip file (temporary file)
    """
    # Create a temporary file for the modified zip
    temp_fd, temp_path = tempfile.mkstemp(suffix=".zip", prefix=f"agent_{agent_zip_path.stem}_with_sdms_")
    os.close(temp_fd)
    output_path = Path(temp_path)

    logger.info(
        "Injecting SDMs into agent package",
        agent_zip=str(agent_zip_path),
        num_sdms=len(sdm_source_dirs),
        output=str(output_path),
    )

    # Create a temporary directory for extraction and modification
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path_dir = Path(temp_dir)
        extract_dir = temp_path_dir / "agent_extracted"
        extract_dir.mkdir()

        # Extract the original agent zip
        with zipfile.ZipFile(agent_zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        # Create semantic_data_models directory in the agent package
        sdms_dir = extract_dir / "semantic_data_models"
        sdms_dir.mkdir(exist_ok=True)

        # Copy each SDM file and collect names for agent-spec.yaml
        sdm_file_names = []
        for sdm_source_dir in sdm_source_dirs:
            if not sdm_source_dir.exists():
                logger.warning(
                    "SDM source directory not found, skipping",
                    sdm_dir=str(sdm_source_dir),
                )
                continue

            # Look for sdm.yml or sdm.yaml in the source directory
            sdm_file = None
            for filename in ["sdm.yml", "sdm.yaml"]:
                candidate = sdm_source_dir / filename
                if candidate.exists():
                    sdm_file = candidate
                    break

            if not sdm_file:
                logger.warning(
                    "No sdm.yml or sdm.yaml found in directory, skipping",
                    sdm_dir=str(sdm_source_dir),
                )
                continue

            # Create a unique filename for this SDM
            # e.g., bird_california_schools ->
            #       bird_california_schools_sdm.yml
            sdm_name = sdm_source_dir.name
            dest_filename = f"{sdm_name}_sdm.yml"
            dest_path = sdms_dir / dest_filename

            # Copy the SDM file
            shutil.copy2(sdm_file, dest_path)
            sdm_file_names.append(dest_filename)
            logger.debug(
                "Injected SDM",
                sdm_name=sdm_name,
                source=str(sdm_file),
                dest=str(dest_path),
            )

        # Update agent-spec.yaml to register the SDMs
        agent_spec_path = extract_dir / "agent-spec.yaml"
        if agent_spec_path.exists():
            _update_agent_spec_with_sdms(agent_spec_path, sdm_file_names)
        else:
            logger.warning(
                "agent-spec.yaml not found in agent package",
                extract_dir=str(extract_dir),
            )

        # Create the new zip file
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zip_out:
            for file_path in extract_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(extract_dir)
                    zip_out.write(file_path, arcname)

    logger.info(
        "Successfully created agent package with injected SDMs",
        output=str(output_path),
        num_sdms=len(sdm_file_names),
        sdm_files=sdm_file_names,
    )

    return output_path


def _update_agent_spec_with_sdms(agent_spec_path: Path, sdm_file_names: list[str]) -> None:
    """
    Update agent-spec.yaml to include semantic-data-models section.

    Args:
        agent_spec_path: Path to agent-spec.yaml
        sdm_file_names: List of SDM filenames to register
    """
    logger.info(
        "Updating agent-spec.yaml with SDMs",
        agent_spec=str(agent_spec_path),
        num_sdms=len(sdm_file_names),
    )

    # Read the current agent-spec.yaml
    with open(agent_spec_path) as f:
        agent_spec = yaml.safe_load(f)

    # Navigate to the first agent in the spec
    if "agent-package" not in agent_spec:
        logger.error("Invalid agent-spec.yaml: missing 'agent-package' key")
        return

    if "agents" not in agent_spec["agent-package"] or not agent_spec["agent-package"]["agents"]:
        logger.error("Invalid agent-spec.yaml: missing or empty 'agents' list")
        return

    # Update the first agent (most common case is single agent per package)
    agent = agent_spec["agent-package"]["agents"][0]

    # Add or update semantic-data-models section
    # Format: list of dicts with 'name' key
    agent["semantic-data-models"] = [{"name": filename} for filename in sdm_file_names]

    logger.debug(
        "Added semantic-data-models to agent spec",
        agent_name=agent.get("name", "unknown"),
        sdms=sdm_file_names,
    )

    # Write the updated agent-spec.yaml back
    with open(agent_spec_path, "w") as f:
        yaml.dump(agent_spec, f, default_flow_style=False, sort_keys=False)

    logger.info("Successfully updated agent-spec.yaml with SDM references")
