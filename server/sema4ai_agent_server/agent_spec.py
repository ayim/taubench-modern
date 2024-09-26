import base64
import os
import subprocess
from pathlib import Path
from typing import Optional

import aiohttp
import yaml
from pydantic import BaseModel, TypeAdapter

from sema4ai_agent_server.schema import (
    ACTION_PKG_LIST_ADAPTER,
    MODEL,
    ActionPackage,
    Agent,
    AgentMetadata,
    LLMProvider,
)
from sema4ai_agent_server.storage.option import get_storage


class SpecFile(BaseModel):
    name: str
    embedded: bool
    digest: str


SPECFILE_LIST_ADAPTER = TypeAdapter(list[SpecFile])


async def put_agent_from_spec(
    *,
    root_dir: str,
    spec: dict,
    user_id: str,
    agent_id: str,
    public: bool,
    agent_name: str,
    model: MODEL,
    action_server_url: str | None,
    action_server_api_key: str | None,
) -> Agent:
    agent = _replace_dashes_with_underscores(spec["agent-package"]["agents"][0])
    action_packages = []
    for action_package in agent["action_packages"]:
        # When not configured, url and api_key will be set to NOT_CONFIGURED by default
        config = {}
        if action_server_url:
            config["url"] = action_server_url
        if action_server_api_key:
            config["api_key"] = action_server_api_key
        action_packages.append(
            ActionPackage(
                name=action_package["name"],
                organization=action_package["organization"],
                version=action_package["version"],
                whitelist=action_package["whitelist"],
                **config,
            )
        )

    # Create the agent
    return await get_storage().put_agent(
        user_id,
        agent_id,
        public=public,
        name=agent_name,
        description=agent["description"],
        runbook=Path(runbook_file_path(root_dir)).read_text(),
        version=agent["version"],
        model=model,
        architecture=agent["architecture"],
        reasoning=agent["reasoning"],
        action_packages=ACTION_PKG_LIST_ADAPTER.validate_python(action_packages),
        metadata=AgentMetadata.model_validate(agent["metadata"]),
    )


def validate_spec(spec: dict, root_dir: str, model: MODEL) -> None:
    if spec["agent-package"]["spec-version"] != "v2":
        raise Exception("Only v2 spec version is supported")
    if len(spec["agent-package"]["agents"]) != 1:
        raise Exception("Only one agent is supported")

    expected_provider = spec["agent-package"]["agents"][0]["model"]["provider"]
    expected_name = spec["agent-package"]["agents"][0]["model"]["name"]
    if model.provider != expected_provider:
        raise Exception(
            f"Expected provider {expected_provider}, got {model.provider.value}"
        )

    if model.provider != LLMProvider.AZURE and model.name != expected_name:
        raise Exception(f"Expected model {expected_name}, got {model.name}")

    try:
        with open(runbook_file_path(root_dir), "r") as f:
            f.read()
    except FileNotFoundError:
        raise Exception("Runbook not found")
    except IOError:
        raise Exception("Error reading runbook")

    files_in_spec = get_knowledge_files(spec)
    files_in_dir = []
    for _, _, files in os.walk(knowledge_dir(root_dir)):
        files_in_dir = files
    # Compare the number of files in the spec and the knowledge directory
    if len(files_in_spec) != len(files_in_dir):
        raise Exception("Knowledge files mismatch")
    # Compare the files in the spec and the knowledge directory
    for file in files_in_spec:
        if file.name not in files_in_dir:
            raise Exception(
                f"Knowledge file {file.name} not found in knowledge directory"
            )


async def download_agent_package(root_dir: str, package_url: str) -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get(package_url) as resp:
            if resp.status == 200:
                with open(package_file_path(root_dir), "wb") as f:
                    f.write(await resp.read())
            else:
                raise Exception("Failed to download agent package")


async def save_agent_package(root_dir: str, package_base64: str) -> None:
    try:
        content = base64.b64decode(package_base64)
    except Exception:
        raise Exception("Invalid base64 encoded package")
    with open(package_file_path(root_dir), "wb") as f:
        f.write(content)


def get_spec(root_dir: str) -> dict:
    subprocess.run(
        [
            "agent-cli",
            "package",
            "extract",
            "--package",
            package_file_path(root_dir),
            "--output-dir",
            output_dir(root_dir),
        ],
        check=True,
    )
    with open(spec_file_path(root_dir), "r") as f:
        return yaml.safe_load(f)


def get_knowledge_files(spec: dict) -> list[SpecFile]:
    return SPECFILE_LIST_ADAPTER.validate_python(
        spec["agent-package"]["agents"][0]["knowledge"]
    )


def _replace_dashes_with_underscores(spec: dict) -> dict:
    def recursive_replace(d):
        if isinstance(d, dict):
            return {k.replace("-", "_"): recursive_replace(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [recursive_replace(item) for item in d]
        else:
            return d

    return recursive_replace(spec)


def output_dir(root_dir: str) -> str:
    return os.path.join(root_dir, "output")


def knowledge_dir(root_dir: str) -> str:
    return os.path.join(output_dir(root_dir), "knowledge")


def package_file_path(root_dir: str) -> str:
    return os.path.join(root_dir, "agent_package.zip")


def spec_file_path(root_dir: str) -> str:
    return os.path.join(output_dir(root_dir), "agent-spec.yaml")


def runbook_file_path(root_dir: str) -> str:
    return os.path.join(output_dir(root_dir), "runbook.md")
