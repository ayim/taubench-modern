from agent_platform.core.thread.content.base import ThreadMessageContent
from agent_platform.core.thread.content.thought import ThreadThoughtContent


class TestThreadThoughtContent:
    def test_create_valid_thought_content(self):
        thought = ThreadThoughtContent(thought="I am thinking about something.")
        assert thought.kind == "thought"
        assert thought.thought == "I am thinking about something."

    def test_thought_as_text_content(self):
        thought = ThreadThoughtContent(thought="Secret internal note.")
        text_version = thought.as_text_content()
        assert isinstance(text_version, str)
        assert text_version == "Secret internal note."

    def test_model_validation_ignores_unknown_fields(self):
        data = {
            "content_id": "content-1",
            "kind": "thought",
            "thought": "legacy",
            "extras": "ignore me",
            "complete": True,
        }
        result = ThreadMessageContent.model_validate(data)
        assert isinstance(result, ThreadThoughtContent)
        assert result.thought == "legacy"
