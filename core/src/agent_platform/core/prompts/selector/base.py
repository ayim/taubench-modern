from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromptSelectionRequest:
    """
    A request for selecting a prompt to use when generating a response from a model.
    """

    direct_prompt_name: str | None = None
    provider: str | None = None
    model_family: str | None = None
    model_name: str | None = None

    def is_empty(self) -> bool:
        return (
            self.direct_prompt_name is None
            and self.provider is None
            and self.model_family is None
            and self.model_name is None
        )


class PromptSelector(ABC):
    """A base class for implementing logic for selecting a prompt to use
    when generating a response from a model from a list of paths
    pointing to prompts (as yaml files) or directories containing prompts
    relative to a package.
    """

    def __init__(self, prompt_paths: list[str | Path] | None = None, package: str | None = None):
        self.prompt_paths = prompt_paths
        self.package = package
        self._prompts: dict[str, Traversable] | None = None

    def _load_prompts(
        self, prompt_paths: list[str | Path] | None = None, package: str | None = None
    ) -> dict[str, Traversable]:
        """Load the prompts from the given paths and package.

        Args:
            prompt_paths: The paths to the prompts to load.
            package: The package to load the prompts from.

        Returns:
            A dictionary of prompt file names and their contents.
        """
        prompt_paths = prompt_paths or self.prompt_paths or [""]
        package = package or self.package

        resource_root = self._get_resource_root(package)
        return self._collect_prompt_files(resource_root, prompt_paths)

    def _get_resource_root(self, package: str | None) -> Any:
        """Get the resource root for the given package.

        Args:
            package: The package to get the resource root for.

        Returns:
            The resource root.

        Raises:
            ValueError: If the package is not a valid Python package.
        """
        from importlib import resources

        try:
            return resources.files(package)
        except AttributeError as ex:
            raise ValueError(
                f"Failed to locate resource files in package {package}. "
                "Are you sure it's a valid Python package?",
            ) from ex

    def _collect_prompt_files(
        self, resource_root: Traversable, prompt_paths: list[str | Path]
    ) -> dict[str, Traversable]:
        """Collect prompt files from the given resource root and paths.

        Args:
            resource_root: The resource root to collect files from.
            prompt_paths: The paths to collect files from.

        Returns:
            A dictionary of prompt file names and a Traversable to the file.
        """
        prompt_files: dict[str, Traversable] = {}

        for prompt_path in prompt_paths:
            resource_path = resource_root / str(prompt_path)

            if resource_path.is_file():
                prompt_files[resource_path.name] = resource_path
            elif resource_path.is_dir():
                prompt_files.update(
                    {
                        file.name: file
                        for file in resource_path.iterdir()
                        if file.is_file()
                        and (file.name.endswith(".yaml") or file.name.endswith(".yml"))
                    }
                )

        return prompt_files

    @property
    def prompts(self) -> dict[str, Traversable]:
        if self._prompts is None:
            self._prompts = self._load_prompts()
        return self._prompts

    @abstractmethod
    def select_prompt(
        self,
        request: PromptSelectionRequest,
        **kwargs,
    ) -> tuple[str, Traversable]:
        """Select a prompt to use when generating a response from a model.

        Args:
            request:  A request for selecting a prompt to use when generating a
                      response from a model.
            **kwargs: Additional keyword arguments.

        Returns:
            A tuple of the name of the selected prompt and the prompt content (without
            formatting).
        """
        pass
