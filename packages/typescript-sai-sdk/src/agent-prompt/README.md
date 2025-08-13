## Agent Prompt

This module implements the client-side and data structures used to compose and execute prompts against the SAI agent. It provides strongly-typed helpers to build prompt messages, content, tools, and platform configurations, plus a streaming API to apply incremental JSON Patch operations as results are produced.

The API is validated with `zod` schemas to ensure prompt requests and responses conform to the expected shapes.

### Key concepts

- PromptRequest: an object that wraps a platform configuration with a `prompt` description. See `platform_config` and `prompt` schemas in `./index`.
- Prompt: a collection of optional fields that influence generation, including `system_instruction`, `messages`, `tools`, `tool_choice`, `temperature`, `seed`, `max_output_tokens`, `stop_sequences`, and `top_p`.
- Message and Content: messages can be normal user/agent messages or special messages (e.g., `$conversation_history`, `$documents`, `$memories`). Content supports text, images, tool calls, and tool results.
- Tools: definitions of external tools that the model can call, described by a name, description, and input schema.

### Quick start

- Install and import the module from your TypeScript project (paths may vary depending on your setup). The package entry exports the main types and helpers.

```ts
// Example imports (adjust to your package layout)
import {
  createOpenAIConfig,
  createPromptRequest,
  createTextUserMessage,
  createTool,
} from './modules/sai-sdk/src/agent-prompt';
import { PromptEndpointClient } from './modules/sai-sdk/src/agent-prompt/client';
```

- Build a minimal prompt (no tools):

```ts
const platformConfig = createOpenAIConfig('sk-your-api-key');
const messages = [createTextUserMessage('Hello, how can I assist you today?')];
const promptRequest = createPromptRequest(platformConfig, messages);
```

- Send the prompt to a streaming endpoint:

```ts
const client = new PromptEndpointClient({ baseUrl: 'https://your-sai-server' });

async function run() {
  for await (const patch of client.stream(promptRequest)) {
    // apply patch to a local accumulator if you want to reconstruct state incrementally
    console.log('patch:', patch);
  }
}
run();
```

- Rebuild the final response from streaming patches:

```ts
const finalResponse = await client.streamToResponse(promptRequest);
console.log(finalResponse);
```

### Content helpers

- Create content items that can appear in messages:
  - `createTextContent(text)`
  - `createImageContent(base64Data, mimeType, detail)`
  - `createToolUseContent(toolName, toolCallId, toolInput)`
  - `createToolResultContent(toolName, toolCallId, result)`
- Create messages:
  - `createUserMessage(content)`
  - `createAgentMessage(content)`
  - `createTextUserMessage(text)`
  - `createTextAgentMessage(text)`
- Common convenience: `createPromptRequest(...)` to assemble a full, validated request.

Code references (examples):

```ts
import { createTextContent, createUserMessage, createTextUserMessage } from './modules/sai-sdk/src/agent-prompt';
```

### Tool definitions

- Define a tool with a name, description, and a JSON input schema:

```ts
import { createTool } from './modules/sai-sdk/src/agent-prompt';
const weatherTool = createTool(
  'get_weather',
  'Fetch current weather for a location',
  {
    location: { type: 'string', description: 'City name' },
  },
  ['location'],
);
```

- Tools are supplied to `createPromptRequest` as a second array parameter.

### Platform configurations

- OpenAI

```ts
import { createOpenAIConfig } from './modules/sai-sdk/src/agent-prompt';
const openAiCfg = createOpenAIConfig('sk-...');
```

- Google, Groq, Bedrock follow similar patterns with their respective keys.

### Prompt construction

`createPromptRequest(platformConfig, messages, tools = [], options = {})` builds a validated `PromptRequest`.

- Options include:
  - `systemInstruction?: string`
  - `toolChoice?: 'auto' | 'any' | string` (tool name)
  - `temperature?: number`, `seed?: number`, `maxOutputTokens?: number`, `stopSequences?: string[]`, `topP?: number`

### Streaming API

- `PromptEndpointClient` (in `client.ts`) exposes:

  - `generate(request, model?)` for a standard, non-streaming generation
  - `stream(request, model?)` to receive a streaming sequence of `JsonPatchOperation` objects
  - `streamToResponse(request, model?)` to reconstruct a full `PromptResponse` from streaming patches

- Streaming events use JSON Patch-like operations:

  - `add`, `replace` to set values
  - `remove` to delete fields
  - `inc` to increment numbers
  - `concat_string` to concatenate strings

- Streaming endpoint path:
  - POST `/api/v2/prompts/stream` (with optional `model` query param)
  - POST `/api/v2/prompts/generate` for non-streaming responses

### Types and validation

All shapes are defined in `modules/sai-sdk/src/agent-prompt/index.ts` and exported through the module barrel. Validation uses `zod` and occurs both when constructing a request and when parsing responses.

### Examples (full)

```ts
import {
  createOpenAIConfig,
  createTextUserMessage,
  createTool,
  createPromptRequest,
} from './modules/sai-sdk/src/agent-prompt';
import { PromptEndpointClient } from './modules/sai-sdk/src/agent-prompt/client';

const platform = createOpenAIConfig('sk-...');
const messages = [createTextUserMessage('Hello there')];
const tools = [createTool('echo', 'Echo input', { text: { type: 'string' } }, ['text'])];
const promptReq = createPromptRequest(platform, messages, tools, {
  toolChoice: 'auto',
  temperature: 0.2,
});

const client = new PromptEndpointClient({ baseUrl: 'https://sai.example.com' });

(async () => {
  const response = await client.streamToResponse(promptReq);
  console.log('final response:', response);
})();
```

If you need a quick reference to the individual exports, see the barrel file exports in `./index`.
