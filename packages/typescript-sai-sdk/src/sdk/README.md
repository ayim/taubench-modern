## SAI SDK

The SAI SDK provides a TypeScript surface for defining, configuring, and executing interactive agent "scenarios". It exposes builders for contextual prompts, tools, and scenarios, plus a lightweight configuration singleton to share settings across executions.

Key concepts

- Context: fine-grained control over how the assistant should think and respond. Use the predefined presets or build custom ones with `createContext()`.
- Tool: a small unit that can be plugged into a scenario to perform a specific action or computation. Define tools via `createTool(name, description)`.
- Scenario: a composition of a prompt, a context, and a set of tools. Build with `createScenario(name)` and execute/stream results.
- SDK configuration: a global, singleton configuration object that initializes the prompt endpoint client and stores defaults like the default model and retry options.

Public API (exports)

- Imported from the package root `@sema4ai/sai-sdk` (re-exported from `./src/index.ts`).
- Main namespaces re-exported: `types`, `tools`, `scenarios`, `context`, `config` (via `./sdk/index`).

Getting started

1. Initialize the SDK

```ts
import { SaiSDKConfig, initializeSDK, getSDKConfig } from '@sema4ai/sai-sdk';

const sdkConfig: SaiSDKConfig = {
  promptClient: { baseUrl: 'https://api.example.com' },
  platformConfig: { apiKey: 'YOUR_KEY' },
  defaultModel: 'gpt-4',
  options: { debug: true, timeout: 15000, retry: { attempts: 3, delay: 200 } },
};

initializeSDK(sdkConfig);
const globalConfig = getSDKConfig();
```

2. Inspect or modify the active configuration

```ts
// Read current config
const current = globalConfig.getConfig();

// Update some options without reinitializing
globalConfig.updateConfig({ defaultModel: 'gpt-4-turbo', options: { debug: false } });
```

3. Define and run a scenario

```ts
import { createContext, createScenario, createTool } from '@sema4ai/sai-sdk';

const context = createContext().setTemperature(0.5).setTopP(0.9).build();
const toolEcho = createTool('Echo', 'Echo input back to the caller').build();

const scenario = createScenario('EchoScenario')
  .setContext(context)
  .setPrompt('Please echo the received input')
  .addTool(toolEcho)
  .build();

// Execute synchronously
const response = await scenario.execute();
console.log(response);
```

Or stream progress updates via the builder:

```ts
for await (const patch of scenario.stream()) {
  // apply patches to accumulate partial responses
}
```

Notes

- The SDK re-exports core definitions from `types`, `tools`, `scenarios`, `context`, and `config` for convenient imports.
- Context presets include: `createDefaultContext()`, `createConservativeContext()`, `createBalancedContext()`, and `createCreativeContext()`.
- All builders return fluent interfaces and provide a `build()` method to materialize the corresponding domain object.

API reference

- `SaiSDKConfig` and `initializeSDK(config: SaiSDKConfig): void` (initialization entry point).
- `getSDKConfig(): SaiSDKConfiguration` (singleton accessor).
- `SaiSDKConfiguration` with methods: `initialize`, `getConfig`, `getPromptClient`, `getPlatformConfig`, `getDefaultModel`, `isInitialized`, `reset`, `updateConfig`.
- `createContext()`, `createDefaultContext()`, `createConservativeContext()`, `createBalancedContext()`, `createCreativeContext()`.
- `createTool(name: string, description: string)`, and `createScenario(name: string)`.
- Core types: `Context`, `Scenario`, `ScenarioTool` (as exported from `@sema4ai/sai-sdk`).

For more details, refer to the implementation files under `modules/sai-sdk/src/sdk/`.
