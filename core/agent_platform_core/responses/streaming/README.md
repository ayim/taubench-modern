# Kernel v2 state life-cycle

As I've been working on streaming in the e2e PR, I hit a need to "close the loop" on the cycle of states we encounter. We've discussed this before, but writing it here for all to see; the key responsibility of an agent architecture (AA) is to manage this cycle of states:
Thread state (chat between user and agent); a Thread is a list of thread messages. A thread message has a content array. Content can be of many types (text/thought/attachment/image/audio/etc.)

Thread state often ends up in our generic Prompts. A Prompt is a list of prompt messages. A prompt message has a content array. Content can be of many types here as well. Some thread content types have no easy analogue in our generic Prompt. (We've discussed this before too: a Vega chart in a thread could be an image in a prompt, or text in a prompt, or both. But there's not native "chart" type for prompts in 2025...)

When we have a generic Prompt we send that to some PlatformClient which converts it to a platform-specific prompt. Some platforms/providers/models have prompting constraints that others do not. (Message role interleaving for Claude is one example.)

When the PlatformClient streams back output, it'll come as platform-specific deltas that are converted into deltas for our generic ResponseMessage type. Just like our ThreadMessage and our PromptMessage, a ResponseMessage has a content array with varying types of content. Response content is not one-to-one with Thread content: a textual response might contain a chart, and quick action buttons, and some text, and some thoughts, as one example.

To "close the loop" on getting content from a streamed ResponseMessage back into the Thread and its messages, we need some way to receive streaming data and make reasonable choices as to where that data ends up and how we reshape it back into our thread state. This is the piece I've worked on these past few days.

## The concept of a stream sinks

In an agent arch, I can now write code like the following:

```python
async with platform.stream_response(conversation_prompt, model) as stream:
    await stream.pipe_to(
        *message.as_response_stream_sinks(),
        *state.as_response_stream_sinks(
            selected_fields=["step"],
        ),
    )
```

This streams the output from running conversation_prompt against a particular model on a particular platform and pipes the streaming content to a collection of sinks
These sinks can be very customizable, but reasonable defaults should cover many cases. To write a sink, you have access to this interface (this is a "do nothing" sink example):

```python
class NoOpResponseStreamSink(ResponseStreamSinkBase):
    async def on_message_begin(
        self,
        message: ResponseMessage,
    ) -> None:
        pass

    async def on_stop_reason(
        self,
        stop_reason: str | None,
    ) -> None:
        pass

    async def on_usage(
        self,
        usage: TokenUsage,
    ) -> None:
        pass

    async def on_message_end(
        self,
        message: ResponseMessage,
    ) -> None:
        pass

    async def on_content_begin(
        self,
        idx: int,
        content: ResponseMessageContent,
    ) -> None:
        pass

    async def on_content_end(
        self,
        idx: int,
        final_content: ResponseMessageContent,
    ) -> None:
        pass

    async def on_text_content_begin(
        self,
        idx: int,
        content: ResponseTextContent,
    ) -> None:
        pass

    async def on_text_content_partial(
        self,
        idx: int,
        old_content: ResponseTextContent,
        new_content: ResponseTextContent,
    ) -> None:
        pass

    async def on_text_content_end(
        self,
        idx: int,
        final_content: ResponseTextContent,
    ) -> None:
        pass

    async def on_image_content_begin(
        self,
        idx: int,
        content: ResponseImageContent,
    ) -> None:
        pass

    async def on_image_content_partial(
        self,
        idx: int,
        old_content: ResponseImageContent,
        new_content: ResponseImageContent,
    ) -> None:
        pass

    async def on_image_content_end(
        self,
        idx: int,
        final_content: ResponseImageContent,
    ) -> None:
        pass

    async def on_audio_content_begin(
        self,
        idx: int,
        content: ResponseAudioContent,
    ) -> None:
        pass

    async def on_audio_content_partial(
        self,
        idx: int,
        old_content: ResponseAudioContent,
        new_content: ResponseAudioContent,
    ) -> None:
        pass

    async def on_audio_content_end(
        self,
        idx: int,
        final_content: ResponseAudioContent,
    ) -> None:
        pass

    async def on_document_content_begin(
        self,
        idx: int,
        content: ResponseDocumentContent,
    ) -> None:
        pass

    async def on_document_content_partial(
        self,
        idx: int,
        old_content: ResponseDocumentContent,
        new_content: ResponseDocumentContent,
    ) -> None:
        pass

    async def on_document_content_end(
        self,
        idx: int,
        final_content: ResponseDocumentContent,
    ) -> None:
        pass

    async def on_tool_use_content_begin(
        self,
        idx: int,
        content: ResponseToolUseContent,
    ) -> None:
        pass

    async def on_tool_use_content_partial(
        self,
        idx: int,
        old_content: ResponseToolUseContent,
        new_content: ResponseToolUseContent,
    ) -> None:
        pass

    async def on_tool_use_content_end(
        self,
        idx: int,
        final_content: ResponseToolUseContent,
    ) -> None:
        pass
```

An example of a common (default) sink I have implemented is: "grab any text between <my-tag> and </my-tag> during streaming, incrementally, and put it somewhere"
So, for a message that might have "thoughts" and regular "content" streaming back from an LLM, I have built-in the following to the ThreadMessageWithThreadState:

```python
def as_response_stream_sinks(self) -> list[ResponseStreamSinkBase]:
    """Returns a list of stream sinks for the message."""
    async def _append_content(tag: str, content: str) -> None:
        self.append_content(content)
        await self.stream_delta()

    async def _append_thought(tag: str, content: str) -> None:
        self.append_thought(content)
        await self.stream_delta()

    return [
        XmlTagResponseStreamSink(
            tag="response",
            on_tag_partial=_append_content,
        ),
        XmlTagResponseStreamSink(
            tag="thinking",
            on_tag_partial=_append_thought,
        ),
    ]
```

This means that if a model produces output like:

```txt
<thinking>I should tell the user a funny joke</thinking>
<response>Why did the chicken cross the road?</response>
```

Your ThreadMessageWithThreadState will automatically pick up on a ThreadThoughtContent with the "I should tell the user a funny joke" value and a ThreadTextContent with the "Why did the chicken cross the road?" content. (And, note the stream_delta calls, this sync automatically pushes incremental content deltas to the client for rendering.)

---

I also utilize this XML-style sink to make it easy to update your agent arch state; you can see this here:

```python
def as_response_stream_sinks(
    self,
    selected_fields: list[str] | None = None,
) -> list[ResponseStreamSinkBase]:
    """Returns a list of stream sinks for the state.

    If no fields are selected, a NoOpResponseStreamSink is returned.
    When we see a <field>value</field> in the response stream, the
    corresponding sink will capture the value and set the field value
    on the state object.

    Arguments:
        selected_fields: A list of fields to include in the stream sinks.

    Returns:
        A list of stream sinks (one per selected field).
    """
    if selected_fields is None:
        return [NoOpResponseStreamSink()]

    stream_sinks = []
    for field in selected_fields:

        async def _set_field(_tag: str, content: str, field: str = field) -> None:
            setattr(self, field, content)

        stream_sinks.append(
            XmlTagResponseStreamSink(
                tag=field,
                on_tag_complete=_set_field,
            ),
        )

    return stream_sinks
```

So, if your agent arch has a my_field state and you do state.as_response_stream_sinks(selected_fields=["my_field"]) you'll capture any <my_field>value</my_field> in the models streaming response and use it to update that field value in your state. This coupled with the new capabilities we have around scoped storage in agent arch state should allow slick implementations of some pretty powerful features (like basic memories).
