"""Test toolkit integration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_core.utils.function_calling import (
    convert_to_openai_function,
    convert_to_openai_tool,
)

from sema4ai_agent_server.action_server.toolkits import ActionServerToolkit

from ._fixtures import FakeChatLLMT


def test_initialization() -> None:
    """Test toolkit initialization."""
    ActionServerToolkit(url="http://localhost", llm=FakeChatLLMT())


def test_get_tools_success() -> None:
    # Setup
    toolkit_instance = ActionServerToolkit(
        url="http://example.com", api_key="dummy_key"
    )

    fixture_path = Path(__file__).with_name("_openapi2.fixture.json")

    with patch(
        "sema4ai_agent_server.action_server.toolkits.requests.get"
    ) as mocked_get, fixture_path.open("r") as f:
        data = json.load(f)  # Using json.load directly on the file object
        mocked_response = MagicMock()
        mocked_response.json.return_value = data
        mocked_response.status_code = 200
        mocked_response.headers = {"Content-Type": "application/json"}
        mocked_get.return_value = mocked_response

        # Execute
        tools = toolkit_instance.get_tools()

        # Verify
        assert len(tools) == 5

        tool = tools[2]
        assert tool.name == "add_sheet_rows"
        assert tool.description == (
            "Action to add multiple rows to the Google sheet. "
            "Get the sheets with get_google_spreadsheet_schema if you don't know"
            "\nthe names or data structure.  Make sure the values are in correct"
            """ columns (needs to be ordered the same as in the sample).
Strictly adhere to the schema."""
        )

        openai_func_spec = convert_to_openai_function(tool)

        assert isinstance(
            openai_func_spec, dict
        ), "openai_func_spec should be a dictionary."
        assert set(openai_func_spec.keys()) == {
            "description",
            "name",
            "parameters",
        }, "Top-level keys mismatch."

        assert openai_func_spec["description"] == tool.description
        assert openai_func_spec["name"] == tool.name

        assert isinstance(
            openai_func_spec["parameters"], dict
        ), "Parameters should be a dictionary."

        params = openai_func_spec["parameters"]
        assert set(params.keys()) == {
            "type",
            "properties",
            "required",
        }, "Parameters keys mismatch."
        assert params["type"] == "object", "`type` in parameters should be 'object'."
        assert isinstance(
            params["properties"], dict
        ), "`properties` should be a dictionary."
        assert isinstance(params["required"], list), "`required` should be a list."

        assert set(params["required"]) == {
            "sheet",
            "rows_to_add",
        }, "Required fields mismatch."

        assert set(params["properties"].keys()) == {"sheet", "rows_to_add"}

        desc = "The columns that make up the row"
        expected = {
            "type": "object",
            "properties": {
                "rows": {
                    "description": "The rows that need to be added",
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "columns": {
                                "description": desc,
                                "type": "array",
                                "items": {"type": "string"},
                            }
                        },
                        "required": ["columns"],
                    },
                }
            },
            "required": ["rows"],
        }
        assert params["properties"]["rows_to_add"] == expected


def test_get_tools_with_complex_inputs() -> None:
    toolkit_instance = ActionServerToolkit(
        url="http://example.com", api_key="dummy_key"
    )

    fixture_path = Path(__file__).with_name("_openapi3.fixture.json")

    with patch(
        "sema4ai_agent_server.action_server.toolkits.requests.get"
    ) as mocked_get, fixture_path.open("r") as f:
        data = json.load(f)  # Using json.load directly on the file object
        mocked_response = MagicMock()
        mocked_response.json.return_value = data
        mocked_response.status_code = 200
        mocked_response.headers = {"Content-Type": "application/json"}
        mocked_get.return_value = mocked_response

        # Execute
        tools = toolkit_instance.get_tools()
        assert len(tools) == 4

        tool = tools[0]
        assert tool.name == "create_event"
        assert tool.description == "Creates a new event in the specified calendar."

        all_tools_as_openai_tools = [convert_to_openai_tool(t) for t in tools]
        openai_tool_spec = all_tools_as_openai_tools[0]["function"]

        assert isinstance(
            openai_tool_spec, dict
        ), "openai_func_spec should be a dictionary."
        assert set(openai_tool_spec.keys()) == {
            "description",
            "name",
            "parameters",
        }, "Top-level keys mismatch."

        assert openai_tool_spec["description"] == tool.description
        assert openai_tool_spec["name"] == tool.name

        assert isinstance(
            openai_tool_spec["parameters"], dict
        ), "Parameters should be a dictionary."

        params = openai_tool_spec["parameters"]
        assert set(params.keys()) == {
            "type",
            "properties",
            "required",
        }, "Parameters keys mismatch."
        assert params["type"] == "object", "`type` in parameters should be 'object'."
        assert isinstance(
            params["properties"], dict
        ), "`properties` should be a dictionary."
        assert isinstance(params["required"], list), "`required` should be a list."

        assert set(params["required"]) == {
            "event",
        }, "Required fields mismatch."

        assert set(params["properties"].keys()) == {"calendar_id", "event"}


def test_get_tools_with_multi_level_nesting_and_field_requirements() -> None:
    # Setup
    toolkit_instance = ActionServerToolkit(
        url="http://example.com", api_key="dummy_key"
    )

    fixture_path = Path(__file__).with_name("_openapi4.fixture.json")

    with patch(
        "sema4ai_agent_server.action_server.toolkits.requests.get"
    ) as mocked_get, fixture_path.open("r") as f:
        data = json.load(f)  # Using json.load directly on the file object
        mocked_response = MagicMock()
        mocked_response.json.return_value = data
        mocked_response.status_code = 200
        mocked_response.headers = {"Content-Type": "application/json"}
        mocked_get.return_value = mocked_response

        # Execute
        tools = toolkit_instance.get_tools()

        create_event_tool = tools[0]

        openai_func_spec = convert_to_openai_function(create_event_tool)
        params = openai_func_spec["parameters"]
        recurrence = params["properties"]["event"]["properties"]["recurrence"]

        assert recurrence == {
            "anyOf": [
                {
                    "properties": {
                        "pattern": {
                            "properties": {
                                "dayOfMonth": {
                                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                                    "default": None,
                                    "description": "The day of the month on which the event occurs. Required if type is absoluteMonthly or absoluteYearly",
                                    "title": "Dayofmonth",
                                },
                                "daysOfWeek": {
                                    "description": "A collection of the days of the week on which the event occurs.If type is relativeMonthly or relativeYearly, and daysOfWeek specifies more than one day, the event falls on the first day that satisfies the pattern.Required if type is weekly, relativeMonthly, or relativeYearly",
                                    "items": {"type": "string"},
                                    "title": "Daysofweek",
                                    "type": "array",
                                },
                                "firstDayOfWeek": {
                                    "anyOf": [{"type": "string"}, {"type": "null"}],
                                    "default": None,
                                    "description": "The first day of the week on which the event occurs.Default is sunday. Required if type is weekly",
                                    "title": "Firstdayofweek",
                                },
                                "index": {
                                    "anyOf": [{"type": "string"}, {"type": "null"}],
                                    "default": None,
                                    "description": "Specifies on which instance of the allowed days specified in daysOfWeek the event occurs, counted from the first instance in the month. The possible values are: first, second, third, fourth, last.Default is first. Optional and used if type is relativeMonthly or relativeYearly",
                                    "title": "Index",
                                },
                                "interval": {
                                    "description": "The number of units between occurrences, where units can be in days, weeks, months, or years, depending on the type",
                                    "title": "Interval",
                                    "type": "integer",
                                },
                                "month": {
                                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                                    "default": None,
                                    "description": "The month in which the event occurs. This is a number from 1 to 12",
                                    "title": "Month",
                                },
                                "type": {
                                    "description": "The recurrence pattern type: daily, weekly, absoluteMonthly, relativeMonthly, absoluteYearly, relativeYearly",
                                    "title": "Type",
                                    "type": "string",
                                },
                            },
                            "required": ["type", "interval", "daysOfWeek"],
                            "title": "Pattern",
                            "type": "object",
                        },
                        "range": {
                            "properties": {
                                "endDate": {
                                    "anyOf": [{"type": "string"}, {"type": "null"}],
                                    "default": None,
                                    "description": "The date to stop applying the recurrence pattern. Depending on the recurrence pattern of the event, the last occurrence of the meeting may not be this date.Required if type is endDate.",
                                    "title": "Enddate",
                                },
                                "numberOfOccurrences": {
                                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                                    "default": None,
                                    "description": "The number of times to repeat the event. Required and must be positive if type is numbered.",
                                    "title": "Numberofoccurrences",
                                },
                                "startDate": {
                                    "description": "The date to start applying the recurrence pattern. The first occurrence of the meeting may be this date or later, depending on the recurrence pattern of the event. Must be the same value as the start property of the recurring event.",
                                    "title": "Startdate",
                                    "type": "string",
                                },
                                "type": {
                                    "description": "The recurrence range. The possible values are: endDate, noEnd, numbered.endDate -> Range with end date and requires: type, startDate, endDatenoEnd -> Range without an end date and requires: type, startDatenumbered -> Range with specific number of occurrences and requires: type, startDate, numberOfOccurrences",
                                    "title": "Type",
                                    "type": "string",
                                },
                            },
                            "required": ["type", "startDate"],
                            "title": "Range",
                            "type": "object",
                        },
                    },
                    "required": ["pattern", "range"],
                    "title": "Recurrence",
                    "type": "object",
                },
                {"type": "null"},
            ],
            "default": None,
            "description": "The recurrence of the event",
        }

        attendees = params["properties"]["event"]["properties"]["attendees"]

        assert attendees == {
            "anyOf": [
                {
                    "items": {
                        "properties": {
                            "email": {
                                "description": "The email address of the attendee",
                                "title": "Email",
                                "type": "string",
                            },
                            "name": {
                                "anyOf": [{"type": "string"}, {"type": "null"}],
                                "default": None,
                                "description": "The name of the attendee",
                                "title": "Name",
                            },
                            "type": {
                                "description": "The attendee type: required, optional, resource",
                                "title": "Type",
                                "type": "string",
                            },
                        },
                        "required": ["type", "email"],
                        "title": "AddAttendee",
                        "type": "object",
                    },
                    "type": "array",
                },
                {"type": "null"},
            ],
            "default": None,
            "description": "The list of attendees",
        }
