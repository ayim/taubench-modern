## Agent Prompt

This module provides a complete TypeScript SDK for composing and executing prompts against the SAI Agent Platform. It includes strongly-typed helpers for building messages, content, tools, and platform configurations, plus a streaming API that uses JSON Patch operations for real-time response updates.

All types and requests are validated using Zod schemas to ensure type safety and runtime validation.

### Architecture

The module is organized into several core files:

- **`content.ts`** - Content types (text, images, tool calls/results)
- **`prompt.ts`** - Message types, special messages, and prompt schemas
- **`response.ts`** - Response types and streaming JSON patch operations
- **`tools.ts`** - Tool definition schemas and categories
- **`client.ts`** - `PromptEndpointClient` for API communication
- **`index.ts`** - Barrel exports for all types and schemas

Helper functions are provided in the main SDK's `utils.ts` for easy object creation.

### Key Concepts

- **PromptRequest**: Complete request object containing platform configuration and prompt definition
- **Prompt**: Configuration for generation including system instruction, messages, tools, and parameters
- **Messages**: Regular user/agent messages or special messages (`$conversation_history`, `$documents`, `$memories`)
- **Content**: Text, images, tool calls, or tool results that can appear in messages
- **Tools**: External tool definitions with JSON schemas for input validation
- **Platform Configs**: Authentication and settings for different AI platforms

### Quick Start

```ts
import { PromptEndpointClient, createOpenAIConfig, createTextUserMessage, createPromptRequest } from '@sema4ai/sai-sdk';

// Create platform configuration
const config = createOpenAIConfig('sk-your-api-key');

// Create messages
const messages = [createTextUserMessage('What is the weather like today?')];

// Build the request
const request = createPromptRequest(config, messages);

// Create client and send request
const client = new PromptEndpointClient({ baseUrl: 'https://your-sai-server' });
const response = await client.generate(request);

console.log(response.content[0].text);
```

### Platform Configurations

The SDK supports multiple AI platforms with dedicated helper functions:

```ts
// OpenAI
const openai = createOpenAIConfig('sk-...');

// Azure OpenAI
const azure = createAzureConfig('api-key', 'https://your-resource.openai.azure.com/', 'deployment-name');

// Anthropic Claude
const anthropic = createAnthropicConfig('sk-ant-...');

// AWS Bedrock
const bedrock = createBedrockConfig('access-key-id', 'secret-access-key', 'us-east-1');

// Ollama (local)
const ollama = createOLLamaConfig('http://localhost:11434');

// Snowflake Cortex
const snowflake = createSnowflakeConfig(
  'warehouse',
  'schema',
  'role',
  'account',
  'database',
  'host',
  'password',
  'username',
);
```

### Content and Messages

#### Content Types

```ts
// Text content
const text = createTextContent('Hello world');

// Image content (base64)
const image = createImageContent(base64Data, 'image/jpeg', 'high_res');

// Tool use (when AI calls a tool)
const toolUse = createToolUseContent('get_weather', 'call-123', { location: 'San Francisco' });

// Tool result (response from tool execution)
const toolResult = createToolResultContent('get_weather', 'call-123', 'Sunny, 72°F');
```

#### Message Creation

```ts
// User messages
const userMsg = createUserMessage([createTextContent('Hello')]);
const simpleUserMsg = createTextUserMessage('Hello'); // Convenience function

// Agent messages
const agentMsg = createAgentMessage([createTextContent('Hi there!')]);
const simpleAgentMsg = createTextAgentMessage('Hi there!'); // Convenience function
```

#### Special Messages

Special messages provide access to conversation context, documents, and memories:

```ts
// Include conversation history (last N turns)
const history = createConversationHistoryMessage(10);

// Include specific documents
const docs = createDocumentsMessage(['doc-id-1', 'doc-id-2']);

// Include relevant memories
const memories = createMemoriesMessage(5); // limit to 5 memories
```

### Tool Definitions

Tools allow the AI to call external functions during generation:

```ts
// Define a tool
const weatherTool = createTool(
  'get_weather',
  'Get current weather for a location',
  {
    location: { type: 'string', description: 'City name' },
    units: { type: 'string', enum: ['celsius', 'fahrenheit'], description: 'Temperature units' },
  },
  ['location'], // required fields
  'client-exec-tool', // category
);

// Tool categories:
// - 'internal-tool' - Platform internal tools
// - 'action-tool' - External action tools
// - 'mcp-tool' - MCP protocol tools
// - 'client-exec-tool' - Client-side executable tools
// - 'client-info-tool' - Client information tools
```

### Advanced Prompt Configuration

```ts
const request = createPromptRequest(platformConfig, messages, tools, {
  systemInstruction: 'You are a helpful assistant specialized in weather.',
  toolChoice: 'auto', // 'auto', 'any', or specific tool name
  temperature: 0.7,
  seed: 42,
  maxOutputTokens: 1000,
  stopSequences: ['\n\n'],
  topP: 0.9,
});
```

### Client API

The `PromptEndpointClient` provides three main methods:

#### Standard Generation

```ts
const response = await client.generate(request, 'gpt-4'); // optional model override
```

#### Streaming with JSON Patch

```ts
// Stream individual patches
for await (const patch of client.stream(request)) {
  console.log('Patch:', patch);
  // patch.op can be: 'add', 'replace', 'remove', 'inc', 'concat_string'
  // patch.path indicates where the change occurs
  // patch.value contains the new/additional data
}
```

#### Stream to Complete Response

```ts
// Automatically accumulate patches into final response
const response = await client.streamToResponse(request);
```

### Response Structure

Responses contain rich metadata about the generation:

```ts
interface PromptResponse {
  content: Content[]; // Generated content (text, tool calls, etc.)
  role: 'agent'; // Always 'agent' for responses
  raw_response: any; // Original platform response
  stop_reason: 'STOP' | 'end_turn' | null;
  usage: {
    // Token usage
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  metrics: {
    // Performance metrics
    latencyMs?: number;
  };
  metadata: {
    // Request metadata
    request_id?: string;
    http_status_code?: number;
    host_id?: string;
    token_metrics?: {
      thinking_tokens?: number;
      modality_tokens?: Record<string, number>;
    };
  };
}
```

### Error Handling

The client handles HTTP errors and validation errors:

```ts
try {
  const response = await client.generate(request);
} catch (error) {
  if (error.message.includes('HTTP 400')) {
    console.log('Bad request - check your prompt format');
  } else if (error.message.includes('HTTP 401')) {
    console.log('Authentication failed - check your API key');
  }
}
```

### Complete Example

```ts
import {
  PromptEndpointClient,
  createOpenAIConfig,
  createTextUserMessage,
  createTool,
  createPromptRequest,
  createConversationHistoryMessage,
} from '@sema4ai/sai-sdk';

async function weatherAssistant() {
  // Setup
  const config = createOpenAIConfig(process.env.OPENAI_API_KEY!);
  const client = new PromptEndpointClient({
    baseUrl: 'https://your-sai-server.com',
  });

  // Define tool
  const weatherTool = createTool(
    'get_weather',
    'Get current weather conditions',
    {
      location: { type: 'string', description: 'City name' },
      units: { type: 'string', enum: ['celsius', 'fahrenheit'] },
    },
    ['location'],
  );

  // Create request with conversation history
  const request = createPromptRequest(
    config,
    [createConversationHistoryMessage(5), createTextUserMessage("What's the weather in Tokyo?")],
    [weatherTool],
    {
      systemInstruction: 'You are a weather assistant. Always use the weather tool for current conditions.',
      toolChoice: 'auto',
      temperature: 0.3,
    },
  );

  // Stream the response
  console.log('Weather Assistant Response:');
  for await (const patch of client.stream(request)) {
    if (patch.op === 'concat_string' && patch.path.includes('content/0/text')) {
      process.stdout.write(patch.value);
    }
  }
}
```

### Import Paths

All functions are exported from the main SDK package:

```ts
import {
  // Client
  PromptEndpointClient,

  // Platform configs
  createOpenAIConfig,
  createAzureConfig,
  createAnthropicConfig,
  createBedrockConfig,
  createOLLamaConfig,
  createSnowflakeConfig,

  // Content creation
  createTextContent,
  createImageContent,
  createToolUseContent,
  createToolResultContent,

  // Message creation
  createUserMessage,
  createAgentMessage,
  createTextUserMessage,
  createTextAgentMessage,

  // Special messages
  createConversationHistoryMessage,
  createDocumentsMessage,
  createMemoriesMessage,

  // Tools and requests
  createTool,
  createPromptRequest,

  // Types (if needed)
  type PromptRequest,
  type PromptResponse,
  type Tool,
  type JsonPatchOperation,
} from '@sema4ai/sai-sdk';
```
