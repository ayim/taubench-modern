import difflib
import json
import logging
import pprint
import string
from pathlib import Path
from typing import Any, ClassVar

import pytest
from deepdiff import DeepDiff
from deepdiff.operator import BaseOperatorPlus

from sema4ai_docint.extraction import SyncExtractionClient

BASE_CONFIG = {
    "generate_citations": False,
    "experimental_options": {
        "enrich": {
            "mode": "table",
            "prompt": (
                "CRITICAL: PARSE the entire document. \n"
                "Important: For data in tables, do not skip any rows"
            ),
            "enabled": True,
        },
        "layout_model": "beta",
        "rotate_pages": False,
        "enable_equations": False,
        "enable_checkboxes": False,
        "enable_underlines": False,
        "layout_enrichment": False,
        "return_figure_images": False,
        "native_office_conversion": False,
    },
}


class SimilarStringOperator(BaseOperatorPlus):
    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold  # 0-1 similarity cutoff

    # Only engage for strings
    def match(self, level) -> bool:
        return isinstance(level.t1, str) and isinstance(level.t2, str)

    def give_up_diffing(self, level, diff_instance) -> bool:
        ratio = difflib.SequenceMatcher(None, level.t1, level.t2).ratio()
        if ratio >= self.threshold:
            return True  # Treat as equal
        # Optionally record how close they were
        diff_instance.custom_report_result(
            "strings_not_similar",
            level,
            {"similarity": ratio, "threshold": self.threshold},
        )
        return False  # Let DeepDiff report the change

    # Helps when ignore_order=True
    def normalize_value_for_hashing(self, parent, obj):
        # Only normalize strings for hashing, leave other types unchanged
        if isinstance(obj, str):
            return normalize(obj)
        return obj


class FloatIntOperator(BaseOperatorPlus):
    # Only engage when one value is float and the other is int
    def match(self, level) -> bool:
        return (isinstance(level.t1, float) and isinstance(level.t2, int)) or (
            isinstance(level.t1, int) and isinstance(level.t2, float)
        )

    def give_up_diffing(self, level, diff_instance) -> bool:
        # Convert both to float for comparison
        val1 = float(level.t1)
        val2 = float(level.t2)

        if val1 == val2:
            return True  # Treat as equal

        # Let DeepDiff handle the difference
        return False

    def normalize_value_for_hashing(self, parent, obj):
        # Convert ints to floats for consistent hashing when ignore_order=True
        if isinstance(obj, int):
            return float(obj)
        return obj


def normalize(obj: Any) -> Any:
    """
    Recursively removes punctuation from strings within any nested data structure.
    Works with dicts, lists, and scalar values.

    Args:
        obj: Any Python object that may contain strings

    Returns:
        The same object structure with punctuation removed from all strings
    """
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [normalize(item) for item in obj]
    elif isinstance(obj, str):
        # Remove punctuation
        cleaned = obj.translate(
            str.maketrans("", "", string.punctuation + string.whitespace)
        ).lower()
        # Split on whitespace and join with a single space
        return " ".join(cleaned.split())

    return obj


class TestDocumentExtraction:
    SKIP_TESTS: ClassVar[list] = []

    logger: logging.Logger = logging.getLogger("sema4ai_docint.extraction")

    def _discover_test_directories(self):
        """Discover test directories and their PDFs"""
        test_data_path = Path(__file__).parent / "test-data" / "extraction"
        test_dirs = {}

        for test_dir in test_data_path.iterdir():
            if test_dir.is_dir():
                pdfs = []
                if (test_dir / "data").exists():
                    # Multi-PDF structure
                    pdfs = [f.name for f in (test_dir / "data").glob("*.pdf")]
                elif (test_dir / "data.pdf").exists():
                    # Legacy structure
                    pdfs = ["data.pdf"]

                if pdfs:
                    test_dirs[test_dir.name] = pdfs

        return test_dirs

    def _get_test_paths(self, test_dir: str, pdf_name: str = "data.pdf") -> tuple[Path, Path, Path]:
        """Get input, expected, and actual file paths for a test."""
        base = Path(__file__).parent / "test-data" / "extraction" / test_dir

        if (base / "data").exists():
            # Multi-PDF structure
            input_file = base / "data" / pdf_name
            expected_file = base / "expected" / f"{Path(pdf_name).stem}_expected.json"

            # Create actual directory if it doesn't exist
            actual_dir = base / "actual"
            actual_dir.mkdir(exist_ok=True)
            actual_file = actual_dir / f"{Path(pdf_name).stem}_actual.json"
        else:
            # Legacy single-PDF structure
            input_file = base / "data.pdf"
            expected_file = base / "expected.json"
            actual_file = base / "actual.json"

        return input_file, expected_file, actual_file

    def _load_test_config(self, test_dir: str) -> dict:
        """Load test configuration from file or use defaults."""
        base = Path(__file__).parent / "test-data" / "extraction" / test_dir
        test_config = {"string_similarity_threshold": 0.8}
        test_config_file = base / "test_config.json"
        if test_config_file.exists():
            with open(test_config_file) as f:
                test_config = json.load(f)
        return test_config

    def _load_schema(self, test_dir: str) -> dict:
        """Load schema from file."""
        base = Path(__file__).parent / "test-data" / "extraction" / test_dir
        schema_file = base / "schema.json"
        with open(schema_file) as f:
            return json.load(f)

    def _merge_config(self, base_config: dict, user_config: dict | None) -> dict:
        """
        Merge user configuration with default configuration.

        Args:
            base_config: The base configuration for model
            user_config: The configuration from user (can be None)

        Returns:
            Merged configuration with database config overriding default config
        """
        if not user_config:
            return base_config

        def deep_merge(base: dict, override: dict) -> dict:
            """Recursively merge two dictionaries, with override taking precedence."""
            result = base.copy()
            for key, value in override.items():
                # Special handling for fields that should be completely replaced, not merged
                if key in ["schema", "system_prompt"]:
                    result[key] = value
                elif key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        return deep_merge(base_config, user_config)

    def _run_extraction_test(
        self, client: SyncExtractionClient, test_dir: str, pdf_name: str = "data.pdf"
    ):
        """Helper method supporting multiple PDFs per test directory"""
        if test_dir in self.SKIP_TESTS:
            pytest.skip(f"Skipping test {test_dir}")

        input_file, expected_file, actual_file = self._get_test_paths(test_dir, pdf_name)
        test_config = self._load_test_config(test_dir)
        schema = self._load_schema(test_dir)

        base = Path(__file__).parent / "test-data" / "extraction" / test_dir
        prompt_file = base / "prompt.txt"
        config_file = base / "config.json"

        # Always run extraction to test latest logic
        # Upload
        uploaded_file_url = client.upload(input_file)

        # Support a custom system_prompt. ALWAYS, merge with the default system prompt.

        system_prompt = SyncExtractionClient.DEFAULT_EXTRACT_SYSTEM_PROMPT

        if prompt_file.exists():
            with open(prompt_file) as f:
                system_prompt += "\n" + f.read()

        config = BASE_CONFIG
        if config_file.exists():
            with open(config_file) as f:
                config = self._merge_config(BASE_CONFIG, json.load(f))

        # Parse
        parse_response = client.parse(uploaded_file_url, config=config)
        assert parse_response.job_id, "No job ID returned from parse"

        # Extract
        extract_response = client.extract(
            f"jobid://{parse_response.job_id}",
            schema,
            system_prompt=system_prompt,
            extraction_config=config,
        )

        # Array of results
        results = extract_response.result
        assert len(results) == 1

        # Array of citations (citations are enabled by default)
        # citations = extract_response.citations
        # assert citations is not None
        # assert len(citations) > 0

        # Save results to the specific actual file
        with open(actual_file, "w") as f:
            f.write(json.dumps(results[0], indent=2))

        actual: dict = results[0]  # type: ignore
        self.logger.info(f"Extracted fields for {pdf_name}: {pprint.pformat(actual)}")

        # Validate some extracted fields
        with open(expected_file) as f:
            expectations = json.load(f)

        for key, value in expectations.items():
            assert key in actual, f"Key {key} not found in fields for {pdf_name}"
            # Normalize string values for equality comparison.
            # Reducto is not consistent in extraction with spaces and punctuation.
            actual_value = normalize(actual[key])
            expected_value = normalize(value)
            diff = DeepDiff(
                expected_value,
                actual_value,
                custom_operators=[
                    SimilarStringOperator(threshold=test_config["string_similarity_threshold"]),
                    FloatIntOperator(),
                ],
                ignore_order=True,
                verbose_level=2,
            )
            assert not diff, f"Differences found in {key} for {pdf_name}: {diff}"

        must_not_contain_file = base / "must_not_contain.json"
        if must_not_contain_file.exists():
            with open(must_not_contain_file) as f:
                must_not_contain = json.load(f)
            for key in must_not_contain:
                assert key not in actual, (
                    f"Key {key} should not be present in fields for {pdf_name}"
                )

    def test_sanity_extraction(self, client: SyncExtractionClient):
        """Run a simple sanity check using anahau"""
        self._run_extraction_test(client, "sanity_using_ski_rental")
