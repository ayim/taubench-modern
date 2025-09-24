# Ephemeral Agent SDK

The Ephemeral Agent SDK provides utilities for creating and managing temporary agents via WebSocket streaming. Ephemeral agents are lightweight, temporary agents that can be quickly spun up for specific tasks and automatically cleaned up without persistent storage.

## Features

- **WebSocket Streaming**: Real-time bi-directional communication with agents
- **Event-driven Architecture**: Comprehensive event handling for agent lifecycle and messages
- **Tool Integration**: Support for client-side tools with callback functions
- **Rich Agent Configuration**: Flexible configuration options for agent behavior and capabilities
- **Built-in Agent Setup Assistant**: Pre-configured agent that helps users create other agents
- **Error Handling**: Robust error handling and validation
- **TypeScript Support**: Fully typed with comprehensive interfaces

## Quick Start

```typescript
import {
  createEphemeralAgentClient,
  createBasicAgentConfig,
  createUserMessage,
} from '@sema4ai/sai-sdk/agent-ephemeral';

// Create a client
const client = createEphemeralAgentClient({
  baseUrl: 'wss://api.example.com', // or https://api.example.com
});

// Create agent configuration
const agentConfig = createBasicAgentConfig({
  name: 'temp-assistant',
  description: 'A temporary assistant agent',
  runbook: 'You are a helpful assistant that answers questions briefly.',
  platform_configs: [
    {
      name: 'openai',
      config: {
        api_key: 'your-openai-key',
        model: 'gpt-4',
      },
    },
  ],
});

// Create and start the agent stream
const stream = await client.createStream({
  agent: agentConfig,
  messages: [createUserMessage('Hello, can you help me with something?')],
  handlers: {
    onAgentReady: (event) => {
      console.log('Agent ready:', event.agent_id);
    },
    onMessage: (event) => {
      console.log('Agent response:', event.content);
    },
    onAgentFinished: () => {
      console.log('Agent finished');
      stream.close();
    },
    onAgentError: (event) => {
      console.error('Agent error:', event.error_message);
    },
  },
});

// Send additional messages
stream.sendMessage(createUserMessage('What is the weather like today?'));
```

## Core Concepts

### Ephemeral Agents

Ephemeral agents are temporary agents that:

- Are created on-demand for specific conversations
- Don't persist beyond the session
- Can be configured with custom tools and capabilities
- Support real-time streaming communication

### WebSocket Communication

The SDK uses WebSocket connections for real-time communication:

- Automatic protocol conversion (HTTP/HTTPS → WS/WSS)
- Event-based message handling
- Streaming message content
- Bi-directional communication

## API Reference

### EphemeralAgentClient

The main client class for managing ephemeral agents.

```typescript
const client = createEphemeralAgentClient({
  baseUrl: string;           // WebSocket or HTTP URL
  apiKey?: string;           // Optional API key
  timeout?: number;          // Connection timeout (default: 30000ms)
  headers?: Record<string, string>; // Additional headers
  verbose?: boolean;         // Enable verbose logging
});
```

#### Methods

- `createStream(options)` - Create a new agent stream
- `updateConfig(config)` - Update client configuration
- `getConfig()` - Get current configuration

### Agent Configuration

Create agent configurations using the helper function:

```typescript
const agentConfig = createBasicAgentConfig({
  name: string;              // Agent name
  description: string;       // Agent description
  runbook: string;          // Agent instructions/behavior
  platform_configs: PlatformConfig[]; // Platform configurations (e.g., OpenAI)
  agent_id?: string;        // Optional specific agent ID
});
```

### Messages and Content

Create messages for agent conversations:

```typescript
// Simple text message
const message = createUserMessage('Hello!', 'optional-message-id');

// Message with citations
const messageWithCitations = createUserMessageWithCitations(
  'Here is some information.',
  [createCitation('doc-uri', 0, 10, 'cited text')],
  'message-id',
);
```

### Event Handlers

Handle agent events throughout the lifecycle:

```typescript
const handlers = {
  onAgentReady: (event: AgentReadyEvent) => {
    // Agent is ready, contains run_id, thread_id, agent_id
  },
  onMessage: (event: MessageEvent) => {
    // Streaming message content
  },
  onMessageBegin: (event: MessageEvent) => {
    // Message started streaming
  },
  onMessageContent: (event: MessageEvent) => {
    // Message content chunk
  },
  onMessageEnd: (event: MessageEvent) => {
    // Message finished streaming
  },
  onAgentFinished: (event: AgentFinishedEvent) => {
    // Agent completed successfully
  },
  onAgentError: (event: AgentErrorEvent) => {
    // Agent encountered an error
  },
  onData: (event: DataEvent) => {
    // Custom data from agent
  },
  onOpen: () => {
    // WebSocket connection opened
  },
  onClose: (code?: number, reason?: string) => {
    // WebSocket connection closed
  },
};
```

### Client-side Tools

Define tools that the agent can call on the client:

```typescript
const tools = [
  {
    name: 'search_web',
    description: 'Search the web for information',
    input_schema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query' },
      },
      required: ['query'],
    },
    category: 'client-exec-tool',
    callback: (input: { query: string }) => {
      // Perform web search
      console.log('Searching for:', input.query);
      return { results: ['result1', 'result2'] };
    },
  },
];

const stream = await client.createStream({
  agent: agentConfig,
  client_tools: tools,
  handlers: eventHandlers,
});
```

## Built-in Agent Setup Assistant

The SDK includes a pre-configured agent that helps users create other agents through a guided workflow:

```typescript
import { createSaiAgentSetupConfig, configureSaiAgentSetupTools } from '@sema4ai/sai-sdk/agent-ephemeral/agents';

// Configure the agent setup assistant
const setupAgent = createSaiAgentSetupConfig(
  platformConfigs,
  'setup-agent-id',
  availableActionPackages,
  availableMcpServers,
);

// Configure tools for the setup process
const setupTools = configureSaiAgentSetupTools({
  callbackSetName: (name) => console.log('Agent name set:', name),
  callbackSetDescription: (desc) => console.log('Description set:', desc),
  callbackSetRunbook: (runbook) => console.log('Runbook set:', runbook),
  callbackSetActionPackages: (packages) => console.log('Packages set:', packages),
  callbackSetMcpServers: (servers) => console.log('MCP servers set:', servers),
  callbackSetConversationStarter: (starter) => console.log('Starter set:', starter),
  callbackSetConversationGuide: (guide) => console.log('Guide set:', guide),
  callbackCompleteAgentSetup: () => console.log('Agent setup complete!'),
});

// Use the setup assistant
const setupStream = await client.createStream({
  agent: setupAgent,
  client_tools: setupTools,
  messages: [createUserMessage('I want to create a customer service agent')],
  handlers: setupHandlers,
});
```

## Message Content Types

The SDK supports various message content types:

- **Text Content**: Plain text with optional citations
- **Tool Usage**: Tool execution details
- **Thought Content**: Agent reasoning/thinking
- **Quick Actions**: Interactive buttons/actions
- **Vega Charts**: Data visualizations
- **Attachments**: File attachments

## Error Handling

```typescript
import { isEphemeralAgentStreamError, getEphemeralAgentErrorMessage } from '@sema4ai/sai-sdk/agent-ephemeral';

try {
  const stream = await client.createStream(options);
} catch (error) {
  if (isEphemeralAgentStreamError(error)) {
    console.error('Stream error:', error.code, error.message, error.details);
  } else {
    console.error('General error:', getEphemeralAgentErrorMessage(error));
  }
}
```

## Advanced Usage

### Custom Agent Architecture

```typescript
const customAgent = {
  name: 'advanced-agent',
  description: 'A more advanced agent configuration',
  version: '1.0.0',
  runbook: 'Complex agent instructions...',
  agent_architecture: {
    name: 'custom.architecture',
    version: '2.0.0',
  },
  platform_configs: platformConfigs,
  action_packages: [
    {
      name: 'custom-actions',
      organization: 'my-org',
      version: '1.0.0',
      actions: [{ name: 'custom_action', description: 'Performs custom logic' }],
    },
  ],
  mcp_servers: [
    {
      name: 'custom-mcp-server',
      tools: [{ name: 'mcp_tool', description: 'MCP-based tool' }],
    },
  ],
  advanced_config: {
    architecture: 'agent',
    reasoning: 'enabled',
    recursion_limit: 15,
  },
  mode: 'conversational',
};
```

### Streaming Response Handling

```typescript
let currentMessage = '';

const handlers = {
  onMessageBegin: (event) => {
    currentMessage = '';
    console.log('Message started...');
  },
  onMessageContent: (event) => {
    // Handle streaming content
    if (event.content[0]?.kind === 'text') {
      currentMessage += event.content[0].text;
      updateUI(currentMessage); // Update UI in real-time
    }
  },
  onMessageEnd: (event) => {
    console.log('Complete message:', currentMessage);
    finalizeMessage(currentMessage);
  },
};
```

## TypeScript Types

The SDK is fully typed. Key types include:

- `EphemeralAgentClient` - Main client class
- `UpsertAgentPayload` - Agent configuration
- `ThreadMessage` - Message structure
- `EphemeralEvent` - Base event type
- `ToolDefinitionPayload` - Tool definition
- `EphemeralEventHandlers` - Event handler interface
- `CreateEphemeralStreamOptions` - Stream creation options

## Best Practices

1. **Always handle errors**: Use try-catch blocks and error event handlers
2. **Clean up connections**: Call `stream.close()` when done
3. **Handle all event types**: Implement handlers for lifecycle events
4. **Use tools effectively**: Leverage client-side tools for custom functionality
5. **Validate configurations**: Ensure platform configs and tool definitions are correct
6. **Monitor connection state**: Handle connection opens, closes, and errors appropriately

## License

This module is part of the Sema4.ai Agent Platform SDK.
