import pytest

from agent_server_types_v2.thread.content.thought import ThreadThoughtContent


class TestThreadThoughtContent:
    def test_create_valid_thought_content(self):
        thought = ThreadThoughtContent(thought="I am thinking about something.")
        assert thought.kind == "thought"
        assert thought.thought == "I am thinking about something."

    def test_empty_thought_raises(self):
        with pytest.raises(ValueError, match="Thought value cannot be empty"):
            ThreadThoughtContent(thought="")

    def test_thought_as_text_content(self):
        thought = ThreadThoughtContent(thought="Secret internal note.")
        text_version = thought.as_text_content()
        assert isinstance(text_version, str)
        assert text_version == "Secret internal note."
