# Agent-Server `/api/v2/prompts/` Endpoint

**NOTE:** This is a _prototype_ endpoint, pushed early for the upcoming hackathon. If we find this to
be useful, it will take time and effort (past integration and stabilization of v2).

Just as OpenAI, Anthropic, and others offer "chat completions" API wherein you submit a _Prompt_ and receive a _Response_ of some shape, the v2 `agent-server` exposes a `/api/v2/prompts/generate` and `/api/v2/prompts/stream` endpoint serving the same kind of purpose. The idea behind this endpoint is to allow clients of `agent-server` an opportunity to directly use models from providers _without having to create/insantiate/use an agent_. We hope this will enable clients, like Studio, to quickly prototype and implement more AI-powered features, without the overheading of standing up new services/binaries/or custom backend routes.

## `/api/v2/prompts/generate` (Synchronous)

This endpoint allows you to submit a `Prompt` and blocks until the _full response object is ready._

Example use (OpenAI providers, default model as decided by server):

```bash
curl -X POST 'http://localhost:8000/api/v2/prompts/generate' \
-H 'Content-Type: application/json' \
-d '{
  "platform_config_raw": {
    "kind": "openai",
    "openai_api_key": "REDACTED"
  },
  "prompt": {
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "text": "You are acting as an agent named Test Agent. You are to assist the user with their request."
          }
        ]
      },
      {
        "role": "agent",
        "content": [
          {
            "text": "Understood, I will assist the user with their request."
          }
        ]
      },
      {
        "role": "user",
        "content": [
          {
            "text": "Reply with the answer only, nothing else. What is the capital of the state of Wisconsin, USA?\nThe answer must be one word. Starting with a capital letter, and ending with a period. Emit nothing elseaside from the capital of Wisconsin with a period at the end and starting with a capital letter.\nNOTE: We are not looking for ALL CAPS. Just regular capitalization with a period at the end."
          }
        ]
      }
    ],
    "tools": [],
    "temperature": 0.0,
    "max_output_tokens": 512
  }
}'
```

Example output:

```json
{
  "content": [
    {
      "kind": "text",
      "text": "Madison."
    }
  ],
  "role": "agent",
  "raw_response": null,
  "stop_reason": null,
  "usage": {
    "input_tokens": 131,
    "output_tokens": 4,
    "total_tokens": 135
  },
  "metrics": {},
  "metadata": {},
  "additional_response_fields": {}
}
```

The key part of the prompt is the `messages` array. You can have `user` and `agent` messages. Every message should have a `content` array. Content can be of various kinds, but the most important for basic prompting is `{ text: "My text here." }` content. If you think of a prompt as a "program in natural language" then you use text content to write your program and you'll get text in the response as the "output" of your program.

Prompts can also have tools (shown below) and there are some hyperparameters (`temperature`, etc.) that one can set. For the most part, I'd leave temperature at 0.0, `max_output_tokens` at some reasonably large value (1k, 2k, ish), and ignore most other possible hyperparams.

## `/api/v2/prompts/stream` (Streaming)

This endpoint operates similarly, but will produce `JsonPatch` flavored outputs (with a small `concat_string` extension op) over an SSE stream.

Example use:

```bash
curl -X POST 'http://localhost:8000/api/v2/prompts/stream' \
-H 'Content-Type: application/json' \
-d '{
  "platform_config_raw": {
    "kind": "google",
    "google_api_key": "REDACTED"
  },
  "prompt": {
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "text": "I want to play a number guessing game! Pick a number between 1 and 100."
          }
        ]
      }
    ],
    "tools": [
      {
        "name": "get_range",
        "description": "Get a random number between a minimum and maximum value",
        "input_schema": {
          "type": "object",
          "properties": {
            "min_value": {"type": "integer", "description": "The minimum value of the range"},
            "max_value": {"type": "integer", "description": "The maximum value of the range"}
          },
          "required": ["min_value", "max_value"]
        }
      }
    ],
    "temperature": 0.0,
    "max_output_tokens": 512
  }
}'
```

Example result:

```json
data: {"op": "add", "path": "/role", "value": "agent"}

data: {"op": "add", "path": "/content", "value": [{"kind": "text", "text": "Okay, I can do that! I've picked a number between 1 and 100.\n\n"}]}

data: {"op": "add", "path": "/additional_response_fields", "value": {}}

data: {"op": "add", "path": "/usage", "value": {"input_tokens": 93, "output_tokens": 22, "total_tokens": 291}}

data: {"op": "add", "path": "/metadata", "value": {"token_metrics": {"thinking_tokens": 176, "modality_tokens": {"MediaModality.TEXT": 93}}}}

data: {"op": "add", "path": "/content/1", "value": {"kind": "tool_use", "tool_call_id": "4622468f-53c8-471a-9d62-344b915aea50", "tool_name": "get_range", "tool_input_raw": "{\"max_value\": 100, \"min_value\": 1}"}}

data: {"op": "inc", "path": "/usage/output_tokens", "value": 26}

data: {"op": "inc", "path": "/usage/total_tokens", "value": 26}

data: {"op": "add", "path": "/stop_reason", "value": "STOP"}

data: {"op": "add", "path": "/metadata/sema4ai_metadata", "value": {"platform_name": "google"}}
```

## Tools

Tools are a special way to have the models behind this endpoint use things operated by _the client_. Tools in this API are _not_ executed server-side. (Unlike building an agent where the agent runs, uses tools, and eventually finishes.) Here you, the caller, are responsible for executing tools!

In the above example request, you can see that a tool is name/description/input_schema (loosely). When you execute a tool, you probably want to put the _tool results_ back in your prompt. You can do this by using
two kinds of content in your prompt: a `tool_use` content and a `tool_result` content.

_Tool Use_: This content represents the model _choosing to call a tool you defined_. That's all! It'll have the input that you should parse and pass to your tool, and you're replaying it back into the prompt to preserve the history of what calls were made.

_Tool Result_: This is _after you execute the tool_ and contains the _result_ (as another array of content) from executing the tool. Today, we are only expecting tools to return a single text content with their full result. In the future, we're planning to handle images/other modalities as tool results.

Example (continued from the above with the `get_range` tool):

```bash
curl -X POST 'http://localhost:8000/api/v2/prompts/generate' \
-H 'Content-Type: application/json' \
-d '{
  "platform_config_raw": {
    "kind": "groq",
    "groq_api_key": "REDACTED"
  },
  "prompt": {
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "text": "Pick a random number between 1 and 100 and tell me what it is."
          }
        ]
      },
      {
        "role": "agent",
        "content": [
          {
            "kind": "tool_use",
            "tool_name": "get_range",
            "tool_call_id": "225817d8-8804-4576-a926-98debb930940",
            "tool_input_raw": "{\"max_value\": 100, \"min_value\": 1}"
          }
        ]
      },
      {
        "role": "user",
        "content": [
          {
            "kind": "tool_result",
            "tool_name": "get_range",
            "tool_call_id": "225817d8-8804-4576-a926-98debb930940",
            "content": [
              {
                "text": "73"
              }
            ]
          }
        ]
      }
    ],
    "tools": [
      {
        "name": "get_range",
        "description": "Get a random number between a minimum and maximum value",
        "input_schema": {
          "type": "object",
          "properties": {
            "min_value": {"type": "integer", "description": "The minimum value of the range"},
            "max_value": {"type": "integer", "description": "The maximum value of the range"}
          },
          "required": ["min_value", "max_value"]
        }
      }
    ],
    "temperature": 0.0,
    "max_output_tokens": 512
  }
}'
```

Example Output:

```json
{
  "content": [
    {
      "kind": "text",
      "text": "The random number between 1 and 100 is 73."
    }
  ],
  "role": "agent",
  "raw_response": null,
  "stop_reason": null,
  "usage": {
    "input_tokens": 299,
    "output_tokens": 14,
    "total_tokens": 313
  },
  "metrics": {},
  "metadata": {},
  "additional_response_fields": {}
}
```

## Images

**NOTE:** Not _all_ providers support images. Currently we have support in the Bedrock and OpenAI (and therefore also Azure OpenAI) clients.

In general, going forward, we'll be more in a world where different providers have unique capabilties. Some OpenAI models can take in audio. Some Gemini models can take in Video! Some models can take text and images and produce images. What _modalities_ a given model/provider support is something you need to think through when making direct Prompt requests.

As for **images** we do currently support expressing image data in our generic Prompt type and thank's to Kylie's hard work on the original Bedrock Model Platform Client, we can accept for this provider image content in the following way. (As we add support for other providers, this input shape should remain largely the same.)

Example input:

```bash
export IMAGE_CONTENT="$(base64 -b 0 -i whiteboard.jpg)" && \
echo '{
  "platform_config_raw": {
    "kind": "bedrock",
    "aws_access_key_id": "REDACTED",
    "aws_secret_access_key": "REDACTED",
    "region_name": "us-east-1"
  },
  "prompt": {
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "text": "Get me the text on this whiteboard."
          },
          {
            "kind": "image",
            "value": "'"${IMAGE_CONTENT}"'",
            "mime_type": "image/jpeg",
            "sub_type": "base64",
            "detail": "high_res"
          }
        ]
      }
    ],
    "tools": [],
    "temperature": 0.0,
    "max_output_tokens": 1024
  }
}' | \
curl -X POST 'http://localhost:8000/api/v2/prompts/generate' \
-H 'Content-Type: application/json' \
--data @-
```

Example output:

```json
{
  "content": [
    {
      "kind": "text",
      "text": "The whiteboard shows various technical diagrams and text including:\n\nOn the left (in green):\n- \"CREATE AGENT (SAI)\"\n- \"Studio\"\n- \"Agent Server\"\n- \"Action Server\"\n- \"GET POST\"\n\nIn the middle:\n- A triangle labeled \"Damage API\"\n- \"Stable\" and \"Unstable\" curves\n- \"Sox System\"\n\nOn the right (in red and blue):\n- References to \"ASV2\"\n- \"Studio\"\n- \"DR\"\n- \"NCP\"\n- \"KB\"\n- Various interconnected shapes and arrows showing what appears to be a system architecture or workflow diagram\n\nThe diagram seems to be depicting some kind of software system architecture with various components and their interactions."
    }
  ],
  "role": "agent",
  "raw_response": null,
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 1583,
    "output_tokens": 169,
    "total_tokens": 1752
  },
  "metrics": {
    "latencyMs": 9675
  },
  "metadata": {
    "request_id": "482c3bc6-7876-4475-bb3b-c2fd809edfc4",
    "http_status_code": 200,
    "http_headers": {
      "date": "Thu, 08 May 2025 15:34:27 GMT",
      "content-type": "application/json",
      "content-length": "945",
      "connection": "keep-alive",
      "x-amzn-requestid": "482c3bc6-7876-4475-bb3b-c2fd809edfc4"
    },
    "retry_attempts": 0,
    "host_id": null
  },
  "additional_response_fields": {
    "trace": null,
    "performanceConfig": null
  }
}
```

Supported model/provider combos: `Bedrock` with default `claude-3-7-sonnet` model and older `claude-3-5-sonnet` model. OpenAI with `o4-mini(-high|-low)`, `gpt-4o(-mini)`, `gpt-4.1(-mini|-nano)` (and a few other older models). See the [Example TypeScript Client](./prompt-endpoint-examples/README.md) for an in depth look at streaming a prompt with an image in it. (And streaming responses from the prompt endpoint, in general.)

## Audio

**NOTE:** Not _all_ providers support audio. Stick to OpenAI for now and support for more will come in time. For OpenAI, you can _only_ use the `gpt-4o-audio` model to stream audio.

For an example of streaming a prompt with audio content, see the [Example TypeScript Client](./prompt-endpoint-examples/README.md).

## Picking a non-default model

In the prompt endpoint, you can use `/api/v2/prompts/generate?model=model-name` to set the exact model. If you don't set the exact model as a query parameter, we'll give you the default model for that provider.

Example request (note the `?model=o3-mini-high`):

```bash
curl -X POST 'http://localhost:8000/api/v2/prompts/stream?model=o3-mini-high' \
-H 'Content-Type: application/json' \
-d '{
  "platform_config_raw": {
    "kind": "openai",
    "openai_api_key": "REDACTED"
  },
  "prompt": {
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "text": "Write me a short proof the the square root of 2 is irrational."
          }
        ]
      }
    ],
    "tools": [],
    "temperature": 0.0,
    "max_output_tokens": 1024
  }
}'
```
