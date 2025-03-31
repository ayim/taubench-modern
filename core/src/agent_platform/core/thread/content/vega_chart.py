import json
from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.thread.content.base import ThreadMessageContent
from agent_platform.core.utils import assert_literal_value_valid


@dataclass
class ThreadVegaChartContent(ThreadMessageContent):
    """Represents a Vega or Vega-Lite chart content component in the thread.

    This class handles Vega or Vega-Lite chart content, ensuring that the chart
    is properly typed.
    """

    chart_spec_raw: str = field(
        metadata={
            "description": "The Vega or Vega-Lite chart spec JSON "
                "(as a string) to display",
        },
    )
    """The Vega or Vega-Lite chart spec JSON (as a string) to display"""

    kind: Literal["vega_chart"] = field(  # type: ignore
        default="vega_chart",
        metadata={"description": "Content kind: always 'vega_chart'"},
        init=False,
    )
    # Type ignore here as we can narrow the kind to Literal["vega_chart"]
    """Content kind: always 'vega_chart'"""

    sub_type: Literal["vega", "vega-lite"] = field(
        default="vega",
        metadata={"description": "The type of the chart, either 'vega' or 'vega-lite'"},
    )
    """The type of the chart, either 'vega' or 'vega-lite'"""

    completed: bool = field(
        default=False,
        metadata={"description": "Whether the chart is completed"},
    )
    """Whether the chart is completed"""

    _chart_spec: dict | None = field(default=None, init=False)

    @property
    def chart_spec(self) -> dict:
        """The Vega or Vega-Lite chart spec JSON (parsed as a dictionary) to display"""
        if self._chart_spec is None:
            raise ValueError("Chart spec has not been parsed yet")
        return self._chart_spec

    def __post_init__(self) -> None:
        """Validates the content type and chart content after initialization.

        Raises:
            AssertionError: If the type or sub_type fields don't match their literals.
            ValueError: If the chart spec is invalid or empty.
        """
        if not isinstance(self.chart_spec_raw, str):
            raise ValueError("Chart spec value must be a string")

        assert_literal_value_valid(self, "kind")
        assert_literal_value_valid(self, "sub_type")

        if not self.chart_spec_raw:
            raise ValueError("Chart spec value cannot be empty")

        # We MUST have a parseable JSON chart spec
        try:
            parsed_spec = json.loads(self.chart_spec_raw)
        except json.JSONDecodeError as e:
            raise ValueError("Chart spec value must be a valid JSON string") from e

        # Validate schema (if it's missing, we can add it based on sub_type)
        if "$schema" not in parsed_spec:
            # https://vega.github.io/schema/vega(-lite)/v5.json
            parsed_spec["$schema"] = (
                f"https://vega.github.io/schema/{self.sub_type}/v5.json"
            )

        schema = parsed_spec["$schema"]
        if not isinstance(schema, str):
            raise ValueError("Chart spec $schema field must be a string")

        # Make sure the schema is a valid URL
        if not schema.startswith("http"):
            raise ValueError("Chart spec $schema field must be a valid URL")

        # Make sure schema ends in .json (it's a json schema file)
        if not schema.endswith(".json"):
            raise ValueError("Chart spec $schema field must end in .json")

        # Validate schema matches sub_type
        if self.sub_type == "vega" and "schema/vega-lite/" in schema.lower():
            raise ValueError("Schema indicates Vega-Lite but sub_type is set to 'vega'")
        elif self.sub_type == "vega-lite" and "schema/vega/" in schema.lower():
            raise ValueError("Schema indicates Vega but sub_type is set to 'vega-lite'")

        # Use object.__setattr__ to bypass the frozen restriction
        object.__setattr__(self, "_chart_spec", parsed_spec)

    def as_text_content(self) -> str:
        """Converts the chart content to a text content component."""
        chart_spec_clean = json.dumps(self.chart_spec, indent=2)
        return f"```{self.sub_type}\n{chart_spec_clean}\n```"

    def model_dump(self) -> dict:
        """Serializes the vega chart content to a dictionary.
        Useful for JSON serialization."""
        return {
            **super().model_dump(),
            "chart_spec_raw": self.chart_spec_raw,
            "sub_type": self.sub_type,
            "completed": self.completed,
        }

    def model_dump_json(self) -> str:
        """Serializes the vega chart content to a JSON string."""
        return json.dumps(self.model_dump())

    @classmethod
    def model_validate(cls, data: dict) -> "ThreadVegaChartContent":
        """Create a thread vega chart content from a dictionary."""
        return cls(**data)


ThreadMessageContent.register_content_kind("vega_chart", ThreadVegaChartContent)
