"""BIRD dataset resolver for fetching from Hugging Face or local paths.

This module handles acquiring BIRD benchmark datasets from various sources:
- Hugging Face datasets for questions/SQL metadata (e.g., birdsql/bird_sql_dev_20251106)
- Local file paths for SQLite database files
- Google Drive for database downloads (manual process)

IMPORTANT: The BIRD benchmark stores data in two places:
- Questions/SQL/metadata: Hugging Face (birdsql/*)
- Database files (.sqlite): Google Drive (manual download required)

Reference:
- Hugging Face: https://huggingface.co/birdsql/datasets
- Database Files: https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view
- BIRD Benchmark: https://github.com/AlibabaResearch/DAMO-ConvAI/tree/main/bird
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

# Google Drive link for BIRD database files
BIRD_DATABASES_GDRIVE_URL = "https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view"


class BirdDatasetResolver:
    """Resolver for BIRD benchmark datasets from various sources.

    The BIRD benchmark splits data across two locations:
    - Questions/SQL: Available on Hugging Face (can be auto-downloaded)
    - Database files: Hosted on Google Drive (must be downloaded manually)

    This resolver handles fetching questions from HuggingFace and caching them,
    but requires users to provide the database files locally.
    """

    def __init__(self, cache_dir: Path):
        """Initialize the dataset resolver.

        Args:
            cache_dir: Directory to cache downloaded datasets (e.g., ~/.sema4x/quality/bird)
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def resolve_local(
        self,
        db_path: str | Path,
        questions_json_path: str | Path,
        db_id: str,
    ) -> dict[str, Any]:
        """Resolve dataset from local file paths.

        Args:
            db_path: Path to local SQLite database file
            questions_json_path: Path to local BIRD questions JSON file
            db_id: Database ID to use for filtering questions

        Returns:
            Dictionary with resolved paths and metadata

        Raises:
            FileNotFoundError: If any of the provided paths don't exist
        """
        db_path = Path(db_path)
        questions_json_path = Path(questions_json_path)

        if not db_path.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")
        if not questions_json_path.exists():
            raise FileNotFoundError(f"Questions JSON file not found: {questions_json_path}")

        return {
            "db_path": db_path,
            "questions_json_path": questions_json_path,
            "db_id": db_id,
            "source": "local",
        }

    def resolve_huggingface_questions(
        self,
        dataset_name: str,
        db_id: str,
        db_path: str | Path,
        force_download: bool = False,
    ) -> dict[str, Any]:
        """Resolve questions from Hugging Face with a local database file.

        The BIRD HuggingFace datasets contain questions/SQL/metadata but NOT the
        actual database files. Users must download database files separately from
        Google Drive and provide the path.

        Args:
            dataset_name: Hugging Face dataset name (e.g., "birdsql/bird_sql_dev_20251106")
            db_id: Database ID to extract questions for (e.g., "california_schools")
            db_path: Path to local SQLite database file (downloaded from Google Drive)
            force_download: If True, re-download questions even if cached

        Returns:
            Dictionary with resolved paths and metadata

        Raises:
            ImportError: If datasets library is not installed
            FileNotFoundError: If the database file doesn't exist
            ValueError: If no questions found for the db_id
        """
        db_path = Path(db_path)

        if not db_path.exists():
            raise FileNotFoundError(
                f"Database file not found: {db_path}\n\n"
                f"BIRD database files must be downloaded separately from Google Drive:\n"
                f"  {BIRD_DATABASES_GDRIVE_URL}\n\n"
                f"After downloading, extract and provide the path to the .sqlite file."
            )

        try:
            from datasets import DatasetDict, load_dataset
        except ImportError as e:
            raise ImportError(
                "The 'datasets' library is required to download from Hugging Face. "
                "Install it with: uv pip install -e '.[bird]'"
            ) from e

        # Create cache directory for questions
        dataset_cache_name = dataset_name.replace("/", "_")
        dataset_cache_dir = self.cache_dir / dataset_cache_name / db_id
        questions_cache_path = dataset_cache_dir / "questions.json"

        # Check cache for questions
        if not force_download and questions_cache_path.exists():
            print(f"✓ Using cached questions: {questions_cache_path}")
            return {
                "db_path": db_path,
                "questions_json_path": questions_cache_path,
                "db_id": db_id,
                "source": "huggingface",
                "dataset_name": dataset_name,
                "cached": True,
            }

        print(f"Downloading BIRD questions from Hugging Face: {dataset_name}")
        print("This may take a few minutes on first download...")

        # Download dataset - returns DatasetDict with splits
        dataset_dict = load_dataset(dataset_name)
        if not isinstance(dataset_dict, DatasetDict):
            raise ValueError(f"Expected DatasetDict from {dataset_name}, got {type(dataset_dict)}")

        # Find the appropriate split
        split_name = None
        for key in dataset_dict.keys():
            split_name = key
            break

        if split_name is None:
            raise ValueError(f"Could not find data split in dataset {dataset_name}")

        print(f"  Using dataset split: {split_name}")

        # Extract questions for the specified db_id
        # Note: HuggingFace Dataset rows are dict-like, cast for type checker
        questions: list[dict[str, Any]] = []
        dataset_split = dataset_dict[split_name]

        for row in dataset_split:
            example = cast(dict[str, Any], row)
            if example.get("db_id") == db_id:
                questions.append(
                    {
                        "question_id": example.get("question_id"),
                        "db_id": example.get("db_id"),
                        "question": example.get("question"),
                        "evidence": example.get("evidence", ""),
                        "SQL": example.get("SQL"),
                        "difficulty": example.get("difficulty", "unknown"),
                    }
                )

        if not questions:
            # List available db_ids to help the user
            available_db_ids: set[str] = set()
            for row in dataset_split:
                example = cast(dict[str, Any], row)
                if "db_id" in example:
                    available_db_ids.add(str(example["db_id"]))

            raise ValueError(
                f"No questions found for db_id '{db_id}' in dataset {dataset_name}.\n"
                f"Available db_ids: {sorted(available_db_ids)}"
            )

        print(f"  Found {len(questions)} questions for db_id '{db_id}'")

        # Create cache directory
        dataset_cache_dir.mkdir(parents=True, exist_ok=True)

        # Save questions JSON
        with open(questions_cache_path, "w") as f:
            json.dump(questions, f, indent=2)
        print(f"  ✓ Cached questions: {questions_cache_path}")

        return {
            "db_path": db_path,
            "questions_json_path": questions_cache_path,
            "db_id": db_id,
            "source": "huggingface",
            "dataset_name": dataset_name,
            "cached": False,
        }

    def list_available_db_ids(self, dataset_name: str) -> list[str]:
        """List all available database IDs in a Hugging Face dataset.

        Args:
            dataset_name: Hugging Face dataset name (e.g., "birdsql/bird_sql_dev_20251106")

        Returns:
            Sorted list of available db_ids
        """
        try:
            from datasets import DatasetDict, load_dataset
        except ImportError as e:
            raise ImportError(
                "The 'datasets' library is required to download from Hugging Face. "
                "Install it with: uv pip install -e '.[bird]'"
            ) from e

        print(f"Loading dataset to list db_ids: {dataset_name}")
        dataset_dict = load_dataset(dataset_name)
        if not isinstance(dataset_dict, DatasetDict):
            raise ValueError(f"Expected DatasetDict from {dataset_name}, got {type(dataset_dict)}")

        # Find split
        split_name = None
        for key in dataset_dict.keys():
            split_name = key
            break

        if split_name is None:
            raise ValueError(f"Could not find data split in dataset {dataset_name}")

        # Collect db_ids
        # Note: HuggingFace Dataset rows are dict-like, cast for type checker
        db_ids: set[str] = set()
        dataset_split = dataset_dict[split_name]
        for row in dataset_split:
            example = cast(dict[str, Any], row)
            if "db_id" in example:
                db_ids.add(str(example["db_id"]))

        return sorted(db_ids)
