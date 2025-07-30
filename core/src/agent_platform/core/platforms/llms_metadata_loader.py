import json
import logging
from importlib import resources

from pydantic import ValidationError

from agent_platform.core.platforms.llms_metadata_models import LLMModelMetadata, LLMsMetadata

logger = logging.getLogger(__name__)


class LLMsMetadataLoader:
    """Singleton class for loading and caching LLMs metadata."""

    _instance: "LLMsMetadataLoader | None" = None
    _data: LLMsMetadata | None = None
    _models_by_slug: dict[str, LLMModelMetadata] | None = None

    def __new__(cls) -> "LLMsMetadataLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization of singleton
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

    def load_data(self) -> None:
        logger.info("Loading LLMs metadata...")

        try:
            # Load from package resources (PyInstaller-compatible)
            logger.info("Loading LLMs metadata from package resources")
            package_files = resources.files("agent_platform.core.platforms")
            llms_json_resource = package_files / "llms.json"
            raw_data = json.loads(llms_json_resource.read_text(encoding="utf-8"))

            # Validate and parse the data using Pydantic
            self._data = LLMsMetadata.model_validate(raw_data)

            # Create a lookup dictionary by slug for fast access
            self._models_by_slug = {model.slug: model for model in self._data.data}

            logger.info(f"Successfully loaded {len(self._data.data)} LLM metadata entries")

        except FileNotFoundError:
            logger.error("LLMs metadata file not found")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in LLMs metadata file: {e}")
            raise
        except ValidationError as e:
            logger.error(f"LLMs data validation failed: {e}")
            raise

    def get_model_by_slug(self, slug: str) -> LLMModelMetadata | None:
        if self._models_by_slug is None:
            logger.warning("LLMs metadata not loaded. Call load_data() first.")
            return None

        return self._models_by_slug.get(slug)

    def get_all_models(self) -> list[LLMModelMetadata]:
        if self._data is None:
            logger.warning("LLMs metadata not loaded. Call load_data() first.")
            return []

        return self._data.data

    def is_loaded(self) -> bool:
        return self._data is not None

    @property
    def model_count(self) -> int:
        if self._data is None:
            return 0
        return len(self._data.data)


# Global instance for easy access
llms_metadata_loader = LLMsMetadataLoader()
