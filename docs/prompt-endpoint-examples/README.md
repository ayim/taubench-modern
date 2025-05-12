# Demo TypeScript Client for Prompt Endpoint Streaming

This is a demo TypeScript client for streaming responses from the Prompt Endpoint.

Run `npm i` to install the dependencies. Make sure to set the `OPENAI_API_KEY` environment variable to a valid OpenAI API key.

Usage (images):

```bash
tsx stream-multi-modal.ts -t "What's on this whiteboard; dont make stuff up, just relay the text" -i ex-whiteboard.jpg -m o4-mini-high
```

Example output:

```json
{
  "role": "agent",
  "content": [
    {
      "kind": "text",
      "text": "Here’s a faithful transcription of every bit of text I can read on the board, grouped roughly by its shape and position in the flow:\n\n1. Rectangle (start)  \n   “Distribute forms to student”\n\n2. Rectangle  \n   “Fill out forms”\n\n3. Rectangle  \n   “Validate forms”\n\n4. Diamond  \n   “Valid?”\n\n   – No → loops back to “Fill out forms”  \n   – Yes → proceeds to “Inform Applicant”\n\n5. Rectangle (to the right of “Valid?”)  \n   “Inform Applicant”\n\n6. Diamond  \n   “Eligible Applicant?”\n\n   – No → goes to a rectangle containing just “?”  \n   – Yes → goes to “Create Student Record”\n\n7. Diamond (below “Validate forms,” feeding into the same “Create Student Record” path)  \n   “Student Exists?”\n\n   – Yes → arrow up/right into “Create Student Record”  \n   – No → goes down to “Security Risk?”\n\n8. Diamond  \n   “Security Risk?”\n\n   – Yes → goes to rectangle “Deal with it”  \n   – No → goes to the same “?” rectangle mentioned above\n\n9. Rectangle (that “?” feeds into the rest of the process once resolved)  \n   “?”\n\n10. Rectangle  \n    “Create Student Record”\n\n11. Rectangle  \n    “Enroll in Seminars”\n\n12. Rectangle  \n    “Calculate Fees”\n\n13. Rectangle  \n    “Request Payment”\n\n14. Diamond  \n    “Sufficient Funds?”\n\n    – No → (back to “Request Payment”?)  \n    – Yes → goes to “Collect Fees”\n\n15. Rectangle  \n    “Collect Fees”\n\n16. Rectangle  \n    “Produce Receipt”\n\nThat’s all of the text as it appears, including the decision diamonds, process boxes, loops and the lone “?” box."
    }
  ],
  "additional_response_fields": {
    "id": "chatcmpl-BWWcbvi6CZOUjeYlN9sj8bExd0qXi",
    "model": "o4-mini-2025-04-16"
  },
  "stop_reason": "stop",
  "metadata": {
    "sema4ai_metadata": {
      "platform_name": "openai"
    }
  }
}

```

Usage (audio):

```bash
tsx stream-multi-modal.ts -t "Transcribe this audio" -a ex-audio.mp3 -m gpt-4o-audio
```

**Important:** You _must_ use the `gpt-4o-audio` model to stream audio.

Example output:

```json
{
  "role": "agent",
  "content": [
    {
      "kind": "text",
      "text": "So we decided we had to put in a new well, and somebody asked me why I didn't get it witched. And I didn't know what he was talking about. So they said there's an old fella out here that witches wells, and he'll get you water every time. So I said, okay, how much does he want? He wants ten bucks. I said, bring him on. So we brought this fella out, and he went through his maneuvers with this peach stick, or, I don't remember now if it was a peach stick or a willow. \n\nNew user: \"You used both, though.\"\n\nYeah, either one. One works as good as the other. And he strikes a point where he has a, where he hits water. And he puts a stone down. Then he goes down, uh, in that same line, and where he hits water again, put another stone down. Then he goes at right angles with this, and gets a stone over here, and a stone over here, and where these two lines cross, that's the point.\n\nNew user: \"Kind of be, uh, the kind of...\"\n\nThe veins, the, he said these water veins always run on an angle. Never do north and south or east and west. They're northwest-southeast."
    }
  ],
  "additional_response_fields": {
    "id": "chatcmpl-BWWk5HUEjFQoQqsiif297e1cYkc24",
    "model": "gpt-4o-audio-preview-2024-12-17"
  },
  "stop_reason": "stop",
  "metadata": {
    "sema4ai_metadata": {
      "platform_name": "openai"
    }
  }
}
```

This will stream the response JSON to the console as it's constructed.
