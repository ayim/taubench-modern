# Sema4.ai SDK

[![Node.js Version](https://img.shields.io/badge/node-%3E%3D20.18.1-brightgreen.svg)](https://nodejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7.3-blue.svg)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/license-SEE%20LICENSE-blue.svg)](./LICENSE)

A comprehensive TypeScript SDK for building AI scenarios in the UI using the Sema4.ai platform. The SDK provides three main modules for different use cases: high-level scenario building, direct prompt streaming, and ephemeral agent interactions.

## 🚀 Quick Start

### Installation

```bash
npm install @sema4ai/sai-sdk
```

### Basic Usage

```typescript
import { createScenario, createBalancedContext, initializeSDK, createOpenAIConfig } from '@sema4ai/sai-sdk';

// Initialize the SDK
initializeSDK({
  promptClient: { baseUrl: 'http://localhost:58885' },
  platformConfig: createOpenAIConfig('your-openai-api-key'),
  defaultModel: 'gpt-4',
});

// Create and execute a simple scenario
const scenario = createScenario('Hello World')
  .setPrompt('Explain quantum computing in simple terms.')
  .setContext(createBalancedContext().build())
  .build();

const response = await scenario.execute();
console.log(response);
```

## 📚 Table of Contents

- [Core Modules](#-core-modules)
- [SDK Scenarios](#-sdk-scenarios)
- [Agent Prompt](#-agent-prompt)
- [Ephemeral Agents](#-ephemeral-agents)
- [Configuration](#%EF%B8%8F-configuration)
- [Examples](#-examples)
- [API Reference](#-api-reference)
- [Testing](#-testing)

## 🧩 Core Modules

The SAI SDK consists of three main modules, each designed for different use cases:

| Module               | Purpose                                              | Best For                                    |
| -------------------- | ---------------------------------------------------- | ------------------------------------------- |
| **SDK Scenarios**    | High-level scenario building with tools and contexts | Complex workflows, reusable AI scenarios    |
| **Agent Prompt**     | Direct prompt streaming with platform configurations | Custom prompt handling, streaming responses |
| **Ephemeral Agents** | Temporary agent instances for quick interactions     | Stateless conversations, lightweight agents |

## 🎯 SDK Scenarios

The primary SDK module for building sophisticated AI scenarios with tools, contexts, and execution patterns.

### Key Concepts

- **Scenario**: A composition of prompts, contexts, and tools that can be executed
- **Context**: Fine-grained control over AI behavior (temperature, max tokens, etc.)
- **Tool**: Pluggable functions that agents can call to perform actions
- **Builder Pattern**: Fluent API for constructing scenarios

### Creating Scenarios

```typescript
import { createScenario, createTool, createBalancedContext } from '@sema4ai/sai-sdk';

// Create a custom tool
const weatherTool = createTool('get_weather', 'Get current weather information')
  .addStringProperty('location', 'City name')
  .addBooleanProperty('include_forecast', 'Include 5-day forecast')
  .setRequired(['location'])
  .setCallback(async (input) => {
    // Your weather API integration here
    return JSON.stringify({
      location: input.location,
      temperature: 22,
      condition: 'sunny',
    });
  })
  .build();

// Create a scenario with the tool
const weatherScenario = createScenario('Weather Assistant')
  .setPrompt("What's the weather like in San Francisco? Include forecast if helpful.")
  .setContext(createBalancedContext().setTemperature(0.7).setMaxOutputTokens(500).build())
  .addTool(weatherTool)
  .build();

// Execute the scenario
const result = await weatherScenario.execute();
```

### Context Presets

The SDK provides several context presets for common use cases:

```typescript
import {
  createConservativeContext, // Low temperature, factual responses
  createBalancedContext, // Medium temperature, general purpose
  createCreativeContext, // High temperature, creative content
  createDefaultContext, // Standard settings
} from '@sema4ai/sai-sdk';

// Conservative for facts and analysis
const factualScenario = createScenario('Research Assistant')
  .setContext(createConservativeContext().build())
  .setPrompt('Summarize the latest research on renewable energy.')
  .build();

// Creative for content generation
const creativeScenario = createScenario('Creative Writer')
  .setContext(createCreativeContext().build())
  .setPrompt('Write a short story about time travel.')
  .build();
```

### Streaming Execution

Monitor scenario execution in real-time:

```typescript
const scenario = createScenario('Data Analysis')
  .setPrompt('Analyze the uploaded dataset and provide insights.')
  .setContext(createBalancedContext().build())
  .build();

// Stream execution with real-time updates
for await (const update of scenario.stream()) {
  console.log('Update:', update);

  // Handle specific types of updates
  if (update.type === 'patch' && update.data?.path === '/content/-' && update.data?.value?.kind === 'text') {
    console.log('New content:', update.data.value.text);
  }

  if (update.type === 'tool_call') {
    console.log('Tool called:', update.data.toolName);
  }

  if (update.type === 'final_response') {
    console.log('Final response:', update.data);
  }
}
```

### Tool Chains

Create workflows with sequential tool execution:

```typescript
import { createTool } from '@sema4ai/sai-sdk';

const dataLoader = createTool('load_data', 'Load data from source')
  .addStringProperty('source', 'Data source path')
  .build();

const dataValidator = createTool('validate_data', 'Validate loaded data').build();

const analysisScenario = createScenario('Data Pipeline')
  .setPrompt('Process and analyze the Q1 sales data.')
  .addTool(dataLoader)
  .chainTool(dataValidator, 1000) // Wait 1 second before chaining
  .build();
```

## 🎪 Agent Prompt

Lower-level module for direct prompt streaming with fine-grained control over platform configurations.

### Basic Prompt Streaming

```typescript
import {
  createOpenAIConfig,
  createUserMessage,
  createTextContent,
  createPromptRequest,
  PromptEndpointClient,
} from '@sema4ai/sai-sdk';

// Configure platform
const platformConfig = createOpenAIConfig('your-api-key');

// Create messages
const messages = [createUserMessage([createTextContent('Explain the benefits of TypeScript over JavaScript.')])];

// Build prompt request
const promptRequest = createPromptRequest(platformConfig, messages, [], {
  temperature: 0.7,
  max_output_tokens: 1000,
});

// Stream the response
const client = new PromptEndpointClient({ baseUrl: 'http://localhost:58885' });

for await (const patch of client.stream(promptRequest)) {
  console.log('Streaming patch:', patch);
}

// Or get the complete response
const response = await client.streamToResponse(promptRequest);
console.log('Final response:', response);
```

### Content Types

Support for rich content including text, images, and tool interactions:

```typescript
import {
  createTextContent,
  createImageContent,
  createToolUseContent,
  createUserMessage,
  createAgentMessage,
} from '@sema4ai/sai-sdk';

// Text content
const textMessage = createUserMessage([createTextContent('Please analyze this image:')]);

// Image content
const imageMessage = createUserMessage([
  createTextContent('Analyze this screenshot:'),
  createImageContent(base64ImageData, 'image/png', 'high_res'),
]);

// Tool usage
const toolMessage = createAgentMessage([createToolUseContent('search_web', 'call_123', { query: 'latest AI news' })]);
```

### Platform Configurations

Support for multiple AI platforms:

```typescript
import { createOpenAIConfig, createGoogleConfig, createGroqConfig, createBedrockConfig } from '@sema4ai/sai-sdk';

// OpenAI
const openAI = createOpenAIConfig('sk-...');

// Google AI
const google = createGoogleConfig('your-google-api-key');

// Groq
const groq = createGroqConfig('your-groq-api-key');

// AWS Bedrock
const bedrock = createBedrockConfig('your-aws-credentials', 'region-name');
```

### Tool Definitions

Define tools that agents can call:

```typescript
import { createTool } from '@sema4ai/sai-sdk';

const searchTool = createTool('search_database', 'Search the company database for information')
  .addStringProperty('query', 'Search query')
  .addEnumProperty('category', ['users', 'products', 'orders'], 'Search category')
  .addNumberProperty('limit', 'Result limit (1-100)')
  .setRequired(['query', 'category'])
  .build();

const promptRequest = createPromptRequest(platformConfig, messages, [searchTool], { tool_choice: 'auto' });
```

## 🤖 Ephemeral Agents

Temporary agent instances for quick interactions via WebSocket streaming.

### Basic Usage

```typescript
import { createEphemeralAgentClient, createBasicAgentConfig, createUserMessage } from '@sema4ai/sai-sdk';

const client = createEphemeralAgentClient({
  baseUrl: 'ws://localhost:58885',
});

// Create a basic agent configuration
const agentConfig = createBasicAgentConfig({
  name: 'temp-assistant',
  description: 'A temporary assistant agent',
  runbook: 'You are a helpful assistant',
  openai_api_key: 'your-openai-key',
});

// Create an ephemeral agent stream
const stream = await client.createStream({
  agent: agentConfig,
  messages: [
    createUserMessage([
      {
        content_type: 'text',
        content_id: 'msg-1',
        text: 'Hello, can you help me?',
      },
    ]),
  ],
  handlers: {
    onAgentReady: (event) => {
      console.log('Agent ready:', event.agent_id);
    },
    onMessage: (event) => {
      console.log('Message:', event.content);
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
```

### Error Handling

```typescript
import { isEphemeralAgentStreamError, getEphemeralAgentErrorMessage } from '@sema4ai/sai-sdk';

try {
  const stream = await client.createStream(options);
} catch (error) {
  if (isEphemeralAgentStreamError(error)) {
    const errorMessage = getEphemeralAgentErrorMessage(error);
    console.error('Agent stream error:', errorMessage);
  } else {
    console.error('Unexpected error:', error);
  }
}
```

## ⚙️ Configuration

### SDK Initialization

Initialize the SDK with your platform and client configurations:

```typescript
import { initializeSDK, SaiSDKConfig, createOpenAIConfig } from '@sema4ai/sai-sdk';

const config: SaiSDKConfig = {
  // Prompt client configuration
  promptClient: {
    baseUrl: 'http://localhost:58885',
  },

  // Platform configuration
  platformConfig: createOpenAIConfig(process.env.OPENAI_API_KEY || ''),

  // Default model and options
  defaultModel: 'gpt-4',
  options: {
    debug: false,
    timeout: 15000,
    retry: {
      attempts: 3,
      delay: 1000,
    },
  },
};

initializeSDK(config);
```

### Configuration Management

Access and update configuration dynamically:

```typescript
import { getSDKConfig } from '@sema4ai/sai-sdk';

// Get current configuration
const sdkConfig = getSDKConfig();
const currentConfig = sdkConfig.getConfig();

// Update configuration
sdkConfig.updateConfig({
  defaultModel: 'gpt-4-turbo',
  options: { debug: true },
});

// Check if SDK is initialized
if (sdkConfig.isInitialized()) {
  const promptClient = sdkConfig.getPromptClient();
  const platformConfig = sdkConfig.getPlatformConfig();
}

// Reset configuration
sdkConfig.reset();
```

## 💡 Examples

The SDK comes with comprehensive examples for various use cases. Here are some highlights:

### Educational Assistant

```typescript
const educationalAssistant = createScenario('Learning Helper')
  .setPrompt(
    `Create a study plan for learning machine learning in 30 days.
             Include daily goals, recommended resources, and practice exercises.`,
  )
  .setContext(createBalancedContext().build())
  .addTool(studyPlanGenerator)
  .addTool(quizCreator)
  .addTool(resourceFinder)
  .build();

const studyPlan = await educationalAssistant.execute();
```

### Code Review Assistant

```typescript
const codeReviewer = createScenario('Code Reviewer')
  .setPrompt(
    `Review this TypeScript function for:
             1. Code quality and style
             2. Security vulnerabilities  
             3. Performance optimizations
             4. Test coverage recommendations`,
  )
  .setContext(createConservativeContext().build())
  .addTool(codeAnalyzer)
  .addTool(securityScanner)
  .addTool(performanceProfiler)
  .build();
```

### Content Management System

```typescript
const contentCreator = createScenario('Blog Post Creator')
  .setPrompt('Create a comprehensive blog post about "The Future of AI in Healthcare"')
  .setContext(createCreativeContext().build())
  .addTool(contentPlanner)
  .addTool(seoOptimizer)
  .addTool(socialMediaAdapter)
  .build();
```

## 📖 API Reference

### Core Types

```typescript
// Scenario types
interface Scenario {
  name: string;
  prompt: string;
  context: Context;
  tools: ScenarioTool[];
  verbose?: boolean;
}

// Context configuration
interface Context {
  temperature?: number;
  max_output_tokens?: number;
  top_p?: number;
  seed?: number;
  stop_sequences?: string[];
  system_instruction?: string;
}

// Tool definition
interface ScenarioTool {
  name: string;
  description: string;
  input_schema: {
    type: 'object';
    properties: Record<string, any>;
    required?: string[];
  };
  callback?: (input: any) => Promise<any>;
}
```

### Builder APIs

```typescript
// Scenario builder
interface ScenarioDefinitionBuilder {
  setName(name: string): ScenarioDefinitionBuilder;
  setPrompt(prompt: string): ScenarioDefinitionBuilder;
  setContext(context: Context): ScenarioDefinitionBuilder;
  setVerbose(verbose: boolean): ScenarioDefinitionBuilder;
  addTool(tool: ScenarioTool): ScenarioDefinitionBuilder;
  chainTool(tool: ScenarioTool, delay?: number): ScenarioDefinitionBuilder;
  build(): Scenario;
  toTool(): ScenarioTool;
  execute(): Promise<PromptResponse>;
  stream(): AsyncGenerator<{
    type: 'patch' | 'response_update' | 'tool_call' | 'tool_partial' | 'tool_result' | 'final_response';
    data: any;
    currentResponse?: Partial<PromptResponse>;
  }>;
}

// Tool builder
interface ToolDefinitionBuilder {
  setName(name: string): ToolDefinitionBuilder;
  setDescription(description: string): ToolDefinitionBuilder;
  addStringProperty(name: string, description?: string): ToolDefinitionBuilder;
  addNumberProperty(name: string, description?: string): ToolDefinitionBuilder;
  addBooleanProperty(name: string, description?: string): ToolDefinitionBuilder;
  addArrayProperty(name: string, itemType: any, description?: string): ToolDefinitionBuilder;
  addObjectProperty(
    name: string,
    properties: Record<string, any>,
    requiredFields?: string[],
    description?: string,
  ): ToolDefinitionBuilder;
  addEnumProperty(name: string, values: any[], description?: string): ToolDefinitionBuilder;
  setRequired(fields: string[]): ToolDefinitionBuilder;
  addRequired(field: string): ToolDefinitionBuilder;
  setCallback(callback: (input: any) => any): ToolDefinitionBuilder;
  build(): ScenarioTool;
}

// Context builder
interface ContextDefinitionBuilder {
  setSystemInstruction(instruction: string): ContextDefinitionBuilder;
  setTemperature(temperature: number): ContextDefinitionBuilder;
  setMaxOutputTokens(tokens: number): ContextDefinitionBuilder;
  setTopP(topP: number): ContextDefinitionBuilder;
  setSeed(seed: number): ContextDefinitionBuilder;
  setStopSequences(sequences: string[]): ContextDefinitionBuilder;
  build(): Context;
}
```

### Utility Functions

```typescript
// Scenario utilities
function validateScenario(scenario: Scenario): boolean;
function getScenarioSummary(scenario: Scenario): object;
function cloneScenario(scenario: Scenario): ScenarioDefinitionBuilder;
function mergeContexts(context1: Context, context2: Context): Context;

// Context utilities
function validateContext(context: Context): boolean;

// Tool utilities
function validateTool(tool: ScenarioTool): boolean;
```

## 🧪 Testing

The SDK includes comprehensive tests for all modules and functionality.

### Running Tests

> **Note:** Tests require the Agent Server to be running locally as in Studio
>
> - Go to Agent Server repo
> - Run `make run-as-studio`

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run dev

# Run specific test file
npm test scenarios.test.ts
```

### Test Configuration

Tests require environment variables for integration testing:

```bash
# .env.test
OPENAI_API_KEY=your-test-api-key
SAI_SERVER_URL=http://localhost:58885
```

### Example Test

```typescript
import { createScenario, createConservativeContext } from '@sema4ai/sai-sdk';

describe('Scenario Tests', () => {
  it('should create and validate a basic scenario', () => {
    const scenario = createScenario('Test Scenario')
      .setPrompt('What is 2 + 2?')
      .setContext(createConservativeContext().build())
      .build();

    expect(scenario.name).toBe('Test Scenario');
    expect(scenario.prompt).toBe('What is 2 + 2?');
    expect(validateScenario(scenario)).toBe(true);
  });
});
```

## 🚀 Advanced Usage

### Error Handling

Robust error handling for production use:

```typescript
import { isEphemeralAgentStreamError, getEphemeralAgentErrorMessage } from '@sema4ai/sai-sdk';

try {
  const result = await scenario.execute();
} catch (error) {
  if (isEphemeralAgentStreamError(error)) {
    const errorMessage = getEphemeralAgentErrorMessage(error);
    console.error('Agent stream error:', errorMessage);
  } else {
    console.error('Unexpected error:', error);
  }
}
```

### Performance Optimization

Tips for optimal performance:

```typescript
// Use streaming for long-running scenarios
for await (const update of scenario.stream()) {
  // Process updates incrementally
  if (update.type === 'patch') {
    processUpdate(update.data);
  }
}

// Reuse tool instances across scenarios
const sharedTool = createTool('common_operation', 'Shared functionality').build();

const scenario1 = createScenario('Task 1').addTool(sharedTool).build();
const scenario2 = createScenario('Task 2').addTool(sharedTool).build();

// Configure appropriate context for your use case
const optimizedContext = createContext()
  .setTemperature(0.1) // Lower for consistency
  .setMaxOutputTokens(500) // Limit for faster responses
  .build();
```

## 📝 License

This project is licensed under the terms specified in the LICENSE file.

## 🤝 Contributing

Contributions are welcome! Please see our contribution guidelines for more information.

**Made with ❤️ by the Sema4.ai team**
