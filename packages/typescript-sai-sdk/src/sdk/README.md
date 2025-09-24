# SAI SDK

The SAI SDK is a TypeScript library for building, configuring, and executing AI agent scenarios. It provides a fluent builder API for creating contexts, tools, and scenarios with full support for streaming responses and tool execution.

## Key Concepts

- **Context**: Controls how the agent behaves (temperature, system instructions, output limits, etc.)
- **Tool**: Executable functions that agents can call during scenarios
- **Scenario**: A complete setup combining a user prompt, context configuration, and available tools
- **ScenarioContextBuilder**: Advanced helper for building complex system instructions with structured sections

## Installation

```bash
npm install @sema4ai/sai-sdk
```

## Quick Start

### 1. Initialize the SDK

```ts
import { initializeSDK, createOpenAIConfig } from '@sema4ai/sai-sdk';

initializeSDK({
  platformConfig: createOpenAIConfig('your-openai-api-key'),
  promptClient: { baseUrl: 'http://localhost:58885' }, // Your agent server endpoint
  options: { debug: true },
});
```

### 2. Create and Execute a Simple Scenario

```ts
import { createScenario, createConservativeContext } from '@sema4ai/sai-sdk';

const scenario = createScenario('Geography Quiz')
  .setPrompt('What is the capital of France?')
  .setContext(
    createConservativeContext()
      .setSystemInstruction('You are a geography expert. Provide accurate, concise answers.')
      .build(),
  );

const response = await scenario.execute();
console.log(response.content[0].text); // "The capital of France is Paris."
```

### 3. Create Scenarios with Tools

```ts
import { createTool, createScenario, createBalancedContext } from '@sema4ai/sai-sdk';

// Define a calculator tool
const calculatorTool = createTool('calculator', 'Perform mathematical calculations')
  .addStringProperty('expression', 'Mathematical expression to evaluate')
  .setRequired(['expression'])
  .setCallback((input) => {
    return `Result: ${eval(input.expression)}`;
  })
  .build();

// Create scenario with the tool
const scenario = createScenario('Math Helper')
  .setPrompt('Calculate 15 * 8 + 4')
  .setContext(createBalancedContext().build())
  .addTool(calculatorTool);

const response = await scenario.execute();
```

### 4. Stream Responses with Real-time Updates

```ts
for await (const event of scenario.stream()) {
  switch (event.type) {
    case 'response_update':
      console.log('Response updated:', event.data);
      break;
    case 'tool_call':
      console.log('Tool called:', event.data.toolName);
      break;
    case 'tool_partial':
      console.log('Tool result:', event.data.result);
      break;
    case 'final_response':
      console.log('Final response:', event.data);
      break;
  }
}
```

## Context Presets

The SDK provides four built-in context presets:

```ts
import {
  createDefaultContext, // temperature: 0.0, topP: 0.5, maxTokens: 256
  createConservativeContext, // temperature: 0.2, topP: 0.7, maxTokens: 1024
  createBalancedContext, // temperature: 0.6, topP: 0.8, maxTokens: 2048
  createCreativeContext, // temperature: 0.8, topP: 0.9, maxTokens: 3072, seed: 42
} from '@sema4ai/sai-sdk';
```

### Custom Context

```ts
import { createContext } from '@sema4ai/sai-sdk';

const customContext = createContext()
  .setSystemInstruction('You are a helpful assistant specialized in coding.')
  .setTemperature(0.7)
  .setMaxOutputTokens(1500)
  .setTopP(0.9)
  .setSeed(123)
  .setStopSequences(['###', 'END'])
  .build();
```

## Advanced Context Building

Use `ScenarioContextBuilder` for complex, structured system instructions:

```ts
import { ScenarioContextBuilder } from '@sema4ai/sai-sdk';

const contextBuilder = new ScenarioContextBuilder()
  .addObjectives(['Help users with coding questions', 'Provide clear, executable examples'])
  .addContext({
    userExperience: 'intermediate',
    preferredLanguage: 'TypeScript',
  })
  .addSteps(["1. Understand the user's question", '2. Provide a clear explanation', '3. Give a working code example'])
  .addGuardrails(['Always include error handling', 'Explain complex concepts simply'])
  .addSection('Code Style', ['Use meaningful variable names', 'Add inline comments for complex logic']);

const context = contextBuilder.buildContext('balanced');
```

## Tool Definition

### Basic Tool

```ts
import { createTool } from '@sema4ai/sai-sdk';

const weatherTool = createTool('get_weather', 'Get current weather for a location')
  .addStringProperty('location', 'City name or coordinates')
  .addEnumProperty('units', ['celsius', 'fahrenheit'], 'Temperature units')
  .setRequired(['location'])
  .setCallback(async (input) => {
    // Your weather API call here
    return `Weather in ${input.location}: 22°C, sunny`;
  })
  .build();
```

### Advanced Tool with Complex Schema

```ts
const dataAnalysisTool = createTool('analyze_data', 'Analyze dataset and provide insights')
  .addObjectProperty(
    'dataset',
    {
      source: { type: 'string', description: 'Data source URL or path' },
      format: { type: 'string', enum: ['csv', 'json', 'xlsx'] },
    },
    ['source', 'format'],
  )
  .addArrayProperty('metrics', { type: 'string' }, 'Metrics to calculate')
  .addBooleanProperty('includeVisualizations', 'Generate charts and graphs')
  .setCategory('client-exec-tool')
  .setCallback(async (input) => {
    // Your data analysis logic
    return { summary: 'Analysis complete', charts: [] };
  })
  .build();
```

## Tool Chaining

Chain tools to execute them in sequence:

```ts
const scenario = createScenario('Multi-step Analysis')
  .setPrompt('Analyze the sales data and generate a report')
  .addTool(dataFetchTool)
  .chainTool(dataProcessingTool, 1000) // 1 second delay
  .chainTool(reportGenerationTool)
  .setContext(createBalancedContext().build());
```

## Configuration Management

### Access Current Configuration

```ts
import { getSDKConfig } from '@sema4ai/sai-sdk';

const sdkConfig = getSDKConfig();
const currentConfig = sdkConfig.getConfig();
const promptClient = sdkConfig.getPromptClient();
const platformConfig = sdkConfig.getPlatformConfig();
```

### Update Configuration

```ts
sdkConfig.updateConfig({
  defaultModel: 'gpt-4-turbo',
  options: {
    debug: false,
    timeout: 30000,
    retry: { attempts: 5, delay: 500 },
  },
});
```

## Working with Responses

### Response Structure

```ts
interface PromptResponse {
  role: 'agent';
  content: Array<{
    kind: 'text' | 'tool_use';
    text?: string;
    tool_name?: string;
    tool_call_id?: string;
    tool_input_raw?: any;
  }>;
}
```

### Processing Tool Results

When tools are used, they automatically execute and their results are included in the response flow. The SDK handles:

- Tool invocation with proper input parsing
- Error handling and recovery
- Partial JSON parsing for streaming scenarios
- Tool chaining with configurable delays

## Utility Functions

```ts
import {
  validateScenario,
  validateContext,
  validateTool,
  getScenarioSummary,
  cloneScenario,
  mergeContexts,
} from '@sema4ai/sai-sdk';

// Validate objects
const isValid = validateScenario(myScenario);

// Get scenario information
const summary = getScenarioSummary(scenario);
// { name, prompt, toolCount, hasSystemInstruction, temperature, ... }

// Clone and modify scenarios
const clonedScenario = cloneScenario(originalScenario).setPrompt('Modified prompt').build();

// Merge contexts
const mergedContext = mergeContexts(baseContext, overrideContext);
```

## Error Handling

The SDK provides comprehensive error handling:

```ts
try {
  const response = await scenario.execute();
} catch (error) {
  if (error.message.includes('SDK not initialized')) {
    // Handle initialization error
  } else if (error.message.includes('required')) {
    // Handle validation error
  }
}
```

## Platform Configuration

The SDK supports multiple AI platforms. Use the utility functions to create platform configurations:

```ts
import { createOpenAIConfig } from '@sema4ai/sai-sdk';

const openaiConfig = createOpenAIConfig('your-api-key');
// Add support for other platforms as needed
```

## TypeScript Support

The SDK is fully typed with comprehensive TypeScript definitions:

```ts
import type {
  Context,
  Scenario,
  ScenarioTool,
  SaiSDKConfig,
  ScenarioDefinitionBuilder,
  ToolDefinitionBuilder,
  ContextDefinitionBuilder,
} from '@sema4ai/sai-sdk';
```

## API Reference

### Core Functions

- `initializeSDK(config: SaiSDKConfig): SaiSDKConfiguration`
- `getSDKConfig(): SaiSDKConfiguration`
- `createScenario(name: string): ScenarioDefinitionBuilder`
- `createTool(name: string, description: string): ToolDefinitionBuilder`

### Context Functions

- `createContext(): ContextDefinitionBuilder`
- `createDefaultContext(): ContextDefinitionBuilder`
- `createConservativeContext(): ContextDefinitionBuilder`
- `createBalancedContext(): ContextDefinitionBuilder`
- `createCreativeContext(): ContextDefinitionBuilder`

### Configuration Class

`SaiSDKConfiguration` methods:

- `initialize(config: SaiSDKConfig): SaiSDKConfiguration`
- `getConfig(): SaiSDKConfig`
- `getPromptClient(): PromptEndpointClient`
- `getPlatformConfig(): PlatformConfig`
- `getEphemeralAgentClient(): EphemeralAgentClient`
- `isInitialized(): boolean`
- `reset(): void`
- `updateConfig(updates: Partial<SaiSDKConfig>): void`

For complete API documentation and examples, see the implementation files in the `/sdk` directory.
