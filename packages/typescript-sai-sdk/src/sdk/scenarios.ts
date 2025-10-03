import { createToolResultContent } from '../utils';
import { getSDKConfig } from './config';
import { createContext } from './context';
import { Scenario, Context, ScenarioSchema, ContextSchema, ScenarioTool } from './types';
import { AllMessage, PromptRequest } from '../agent-prompt/prompt';
import { JsonPatchOperation, PromptResponse, ToolResultContent } from '../agent-prompt';
import { parse, Allow } from 'partial-json';
import { logger } from '../logger';

// Type for scenario definition builder
interface ScenarioDefinitionBuilder {
  // Scenario name
  setName(name: string): ScenarioDefinitionBuilder;

  // Context configuration methods
  setContext(context: Context): ScenarioDefinitionBuilder;

  // Verbosity
  setVerbose(verbose: boolean): ScenarioDefinitionBuilder;

  // User prompt
  setPrompt(prompt: string): ScenarioDefinitionBuilder;

  // Tool management methods
  addTool(tool: ScenarioTool): ScenarioDefinitionBuilder;
  chainTool(tool: ScenarioTool, delay?: number): ScenarioDefinitionBuilder;

  // Build the scenario
  build(): Scenario;

  // Convert Scenario to Tool
  toTool(): ScenarioTool;

  // Execute the scenario
  execute(): Promise<PromptResponse>;

  // Stream the scenario with full response handling and tool execution
  stream(): AsyncGenerator<
    {
      type: 'patch' | 'response_update' | 'tool_call' | 'tool_partial' | 'tool_result' | 'final_response';
      data: any;
      currentResponse?: Partial<PromptResponse>;
    },
    void,
    unknown
  >;
}

// Scenario builder class
export class ScenarioBuilder implements ScenarioDefinitionBuilder {
  private scenario: Scenario = {
    name: '',
    prompt: '',
    context: createContext().setTemperature(0.0).setMaxOutputTokens(2048).build(),
    tools: [],
  };

  private toolChains: Map<string, { toolName: string; delay: number } | undefined> = new Map();

  setName(name: string): ScenarioDefinitionBuilder {
    this.scenario.name = name;
    return this;
  }

  setPrompt(prompt: string): ScenarioDefinitionBuilder {
    this.scenario.prompt = prompt;
    return this;
  }

  setContext(context: Context): ScenarioDefinitionBuilder {
    this.scenario.context = context;
    return this;
  }

  setVerbose(verbose: boolean): ScenarioDefinitionBuilder {
    this.scenario.verbose = verbose;
    return this;
  }

  addTool(tool: ScenarioTool): ScenarioDefinitionBuilder {
    if (!this.scenario.tools) {
      this.scenario.tools = [];
    }
    this.scenario.tools.push(tool);
    this.toolChains.set(this.getToolSnakeName(tool.name), undefined);
    return this;
  }

  chainTool(tool: ScenarioTool, delay: number = 0): ScenarioDefinitionBuilder {
    if (!this.scenario.tools) {
      this.scenario.tools = [];
    }
    if (this.scenario.tools.length > 0) {
      const previousTool = this.scenario.tools[this.scenario.tools.length - 1];
      this.toolChains.set(this.getToolSnakeName(previousTool.name), {
        toolName: this.getToolSnakeName(tool.name),
        delay: delay,
      });
    }
    this.scenario.tools.push(tool);
    return this;
  }

  build(): Scenario {
    if (!this.scenario.name) {
      throw new Error('Scenario name is required');
    }
    if (!this.scenario.prompt) {
      throw new Error('Scenario prompt is required');
    }
    if (!this.scenario.context) {
      this.scenario.context = {};
    }
    if (!this.scenario.tools) {
      this.scenario.tools = [];
    }
    return ScenarioSchema.parse(this.scenario);
  }

  toTool(): ScenarioTool {
    return {
      name: this.getToolSnakeName(this.scenario.name),
      description: this.scenario.prompt,
      input_schema: {
        type: 'object',
        properties: {},
        required: [],
      },
      callback: () => {
        return this.execute();
      },
      category: 'client-exec-tool', // We keep this as client-exec-tool as Scenarios can be used as tools that execute client side code
    };
  }

  // =============================
  // ===== Utility methods =====
  // =============================

  private getToolSnakeName(toolName: string): string {
    return toolName
      .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
      .replace(/[\s\-]+/g, '_')
      .toLowerCase();
  }

  // =============================
  // ===== Execution methods =====
  // =============================

  // Execute the scenario
  async execute(): Promise<PromptResponse> {
    // Get the SDK configuration and prompt client
    const sdkConfig = getSDKConfig();
    const promptClient = sdkConfig.getPromptClient();

    // Convert scenario to PromptRequest
    const promptRequest = scenarioToPromptRequest(this.scenario);
    logger.infoIf(this.scenario.verbose, '[ScenarioBuilder.execute] PromptRequest:', promptRequest);

    // Call the Agent Prompt endpoint with the properly mapped request
    const response = await promptClient.generate(promptRequest);
    logger.infoIf(this.scenario.verbose, '[ScenarioBuilder.execute] Response from promptClient.generate:', response);

    // If the response contains tool_use, find all tools and call their callbacks
    const toolUseContents = response.content.filter((content) => content.kind === 'tool_use');
    if (toolUseContents.length > 0) {
      logger.infoIf(this.scenario.verbose, '[ScenarioBuilder.execute] tool_use contents found:', toolUseContents);
      // Flatten all tools in the scenario and call their callbacks
      const callbackResults: ToolResultContent[] = [];

      // Process each tool_use content item
      for (const toolUseContent of toolUseContents) {
        // If the tool_name is not present, return the response
        if (!('tool_name' in toolUseContent)) {
          logger.warnIf(
            this.scenario.verbose,
            '[ScenarioBuilder.execute] tool_use content missing tool_name:',
            toolUseContent,
          );
          return response;
        }

        // Find the tool by name
        const tool = this.scenario.tools.find(
          (t) => this.getToolSnakeName(t.name) === this.getToolSnakeName(toolUseContent.tool_name),
        );
        if (!tool) {
          logger.warnIf(
            this.scenario.verbose,
            '[ScenarioBuilder.execute] No matching tool found for tool_name:',
            toolUseContent.tool_name,
          );
        }
        if (tool && typeof tool.callback === 'function') {
          // Loop through tool chains until all are satisfied
          let toolChainSatisfied = false;
          let currentTool: ScenarioTool = tool;

          while (!toolChainSatisfied) {
            try {
              // Call the callback with the tool input
              const input_raw = toolUseContent.tool_input_raw;
              const callback_input =
                typeof input_raw === 'object' && input_raw !== null
                  ? input_raw
                  : parse(input_raw, Allow.STR | Allow.OBJ);
              logger.infoIf(
                this.scenario.verbose,
                `[ScenarioBuilder.execute] Calling callback for tool: ${currentTool.name} with input:`,
                callback_input,
              );
              const callbackResult = await currentTool.callback(callback_input);
              logger.infoIf(
                this.scenario.verbose,
                `[ScenarioBuilder.execute] Callback result for tool: ${currentTool.name}:`,
                callbackResult,
              );
              callbackResults.push(
                createToolResultContent(currentTool.name, toolUseContent.tool_call_id, callbackResult),
              );

              // Get the next tool in the chain
              const nextToolUUID = this.toolChains.get(this.getToolSnakeName(currentTool.name));
              const nextTool = this.scenario.tools.find(
                (t) => this.getToolSnakeName(t.name) === nextToolUUID?.toolName,
              );
              logger.infoIf(this.scenario.verbose, `[ScenarioBuilder.execute] Next tool: ${JSON.stringify(nextTool)}`);
              if (!nextTool) {
                logger.warnIf(
                  this.scenario.verbose,
                  `[ScenarioBuilder.execute] No next tool in chain for tool: ${currentTool.name}`,
                );
                toolChainSatisfied = true;
                break;
              }
              // Continue with the next tool
              logger.infoIf(
                this.scenario.verbose,
                `[ScenarioBuilder.execute] Chaining to next tool: ${JSON.stringify(nextTool)}`,
              );
              currentTool = nextTool;

              // Wait for the delay before calling the next tool
              await new Promise((resolve) => setTimeout(resolve, nextToolUUID?.delay || 0));
            } catch (error) {
              logger.errorIf(this.scenario.verbose, `Error calling callback for tool ${tool.name}:`, error);
              callbackResults.push(
                createToolResultContent(
                  tool.name,
                  toolUseContent.tool_call_id,
                  `Error in tool ${tool.name}: ${error instanceof Error ? error.message : String(error)}`,
                ),
              );
              logger.warnIf(
                this.scenario.verbose,
                `[ScenarioBuilder.execute] Error in tool callback for ${tool.name}:`,
                error,
              );
              toolChainSatisfied = true;
              break;
            }
          }
        }
      }
    } else {
      logger.warnIf(this.scenario.verbose, '[ScenarioBuilder.execute] No tool_use contents found in response.');
    }

    return response;
  }

  // Stream the scenario with incremental tool execution
  async *stream(): AsyncGenerator<
    {
      type: 'patch' | 'response_update' | 'tool_call' | 'tool_partial' | 'tool_result' | 'final_response';
      data: any;
      currentResponse?: Partial<PromptResponse>;
    },
    void,
    unknown
  > {
    // Get the SDK configuration and prompt client
    const sdkConfig = getSDKConfig();
    const promptClient = sdkConfig.getPromptClient();

    // Convert scenario to PromptRequest
    const promptRequest = scenarioToPromptRequest(this.scenario);
    logger.infoIf(this.scenario.verbose, '[ScenarioBuilder.stream] PromptRequest:', promptRequest);

    // Initialize response accumulator and tool tracking
    let currentResponse: Partial<PromptResponse> = {};
    const toolsInProgress = new Map<
      string,
      {
        toolName: string;
        toolId: string;
        lastInputRaw: string;
        tool: ScenarioTool;
        hasStarted: boolean;
      }
    >();

    try {
      // Stream from the prompt client
      for await (const operation of promptClient.stream(promptRequest)) {
        // Yield the raw patch operation
        yield {
          type: 'patch',
          data: operation,
          currentResponse: { ...currentResponse },
        };

        // Apply the patch to build up the response
        this.applyJsonPatch(currentResponse, operation);

        // Yield the updated response state
        yield {
          type: 'response_update',
          data: currentResponse,
          currentResponse: { ...currentResponse },
        };

        // Check for tool calls and handle incremental execution
        if (currentResponse.content) {
          for (const content of currentResponse.content) {
            logger.infoIf(this.scenario.verbose, '[ScenarioBuilder.stream] content:', content);
            if (content.kind === 'tool_use' && content.tool_name && content.tool_call_id) {
              const toolId = content.tool_call_id;
              const toolName = content.tool_name;
              const currentInputRaw = content.tool_input_raw || '';
              logger.infoIf(this.scenario.verbose, '[ScenarioBuilder.stream] > toolName:', toolName);
              logger.infoIf(this.scenario.verbose, '[ScenarioBuilder.stream] > toolId:', toolId);
              logger.infoIf(this.scenario.verbose, '[ScenarioBuilder.stream] > currentInputRaw:', currentInputRaw);

              // Find the tool definition
              const tool = this.scenario.tools.find((t) => t.name === toolName);
              logger.infoIf(this.scenario.verbose, '[ScenarioBuilder.stream] > tool:', tool);
              if (!tool) {
                logger.warnIf(this.scenario.verbose, `Tool ${toolName} not found in scenario tools`);
                continue;
              }

              // Check if this is a new tool call or an update to existing one
              const existingTool = toolsInProgress.get(toolId);

              if (!existingTool) {
                // New tool call detected
                toolsInProgress.set(toolId, {
                  toolName,
                  toolId,
                  lastInputRaw: currentInputRaw,
                  tool,
                  hasStarted: false,
                });

                // Yield tool call started event
                yield {
                  type: 'tool_call',
                  data: {
                    toolName,
                    toolId,
                    inputRaw: currentInputRaw,
                    isPartial: true,
                  },
                  currentResponse: { ...currentResponse },
                };
              } else if (existingTool.lastInputRaw !== currentInputRaw) {
                // Tool input has been updated, call callback with new data
                existingTool.lastInputRaw = currentInputRaw;

                // Try to parse the current input, handle partial JSON gracefully
                let toolInput: any;
                let isValidJson = false;

                try {
                  if (currentInputRaw.trim()) {
                    toolInput = JSON.parse(currentInputRaw);
                    isValidJson = true;
                  } else {
                    toolInput = null;
                  }
                } catch (error) {
                  // Handle partial JSON - pass raw string and indicate it's partial
                  toolInput = currentInputRaw;
                  isValidJson = false;
                }

                try {
                  // Call the tool callback with current (possibly partial) input
                  const callback_input =
                    typeof toolInput === 'object' && toolInput !== null
                      ? toolInput
                      : parse(toolInput, Allow.STR | Allow.OBJ);
                  logger.infoIf(
                    this.scenario.verbose,
                    `[ScenarioBuilder.stream] Callback input for tool: ${toolName}:`,
                    callback_input,
                  );
                  const toolResult = await tool.callback(callback_input);
                  logger.infoIf(
                    this.scenario.verbose,
                    `[ScenarioBuilder.stream] Tool result for tool: ${toolName}:`,
                    toolResult,
                  );

                  // Yield incremental tool result
                  yield {
                    type: 'tool_partial',
                    data: {
                      toolName,
                      toolId,
                      inputRaw: currentInputRaw,
                      input: toolInput,
                      result: toolResult,
                      isValidJson,
                      isPartial: !isValidJson || !currentInputRaw.trim(),
                    },
                    currentResponse: { ...currentResponse },
                  };

                  existingTool.hasStarted = true;
                } catch (error) {
                  logger.errorIf(this.scenario.verbose, `Error executing tool ${toolName} incrementally:`, error);

                  // Yield partial error event
                  yield {
                    type: 'tool_partial',
                    data: {
                      toolName,
                      toolId,
                      inputRaw: currentInputRaw,
                      input: toolInput,
                      error: error instanceof Error ? error.message : String(error),
                      isValidJson,
                      isPartial: true,
                    },
                    currentResponse: { ...currentResponse },
                  };
                }
              }

              // Mark tool as complete when we have valid JSON (final result already sent via tool_partial)
              if (currentInputRaw.trim() && existingTool && existingTool.hasStarted) {
                try {
                  JSON.parse(currentInputRaw); // Just validate JSON, don't re-execute

                  // Tool is complete - the final result was already sent via tool_partial
                  // Just mark it as complete

                  // Remove from tracking since it's complete
                  toolsInProgress.delete(toolId);
                } catch (jsonError) {
                  // Still not valid JSON, continue tracking
                }
              }
            }
          }
        }
      }

      // Handle any remaining tools in progress - just mark completion, don't re-execute
      for (const [, toolData] of toolsInProgress) {
        if (toolData.hasStarted) {
          logger.warnIf(this.scenario.verbose, `Tool ${toolData.toolName} was still in progress when stream ended`);

          // Yield completion event without re-executing
          yield {
            type: 'tool_result',
            data: {
              toolName: toolData.toolName,
              toolId: toolData.toolId,
              completed: false,
              note: 'Tool execution was interrupted by stream end',
            },
            currentResponse: { ...currentResponse },
          };
        }
      }

      // Yield final response
      yield {
        type: 'final_response',
        data: currentResponse,
        currentResponse: { ...currentResponse },
      };
    } catch (error) {
      logger.errorIf(this.scenario.verbose, 'Error during streaming:', error);
      throw error;
    }
  }

  /**
   * Apply a JSON Patch operation to build up the response
   */
  private applyJsonPatch(obj: any, operation: JsonPatchOperation): void {
    const pathParts = operation.path.split('/').filter((p) => p !== '');

    switch (operation.op) {
      case 'add':
      case 'replace':
        this.setNestedValue(obj, pathParts, operation.value);
        break;
      case 'remove':
        this.removeNestedValue(obj, pathParts);
        break;
      case 'inc':
        const currentValue = this.getNestedValue(obj, pathParts) || 0;
        this.setNestedValue(obj, pathParts, currentValue + operation.value);
        break;
      case 'concat_string':
        // Convert concat_string to replace operation for smoother handling
        const currentString = this.getNestedValue(obj, pathParts) || '';
        const concatenatedValue = currentString + operation.value;
        this.setNestedValue(obj, pathParts, concatenatedValue);
        break;
    }
  }

  private setNestedValue(obj: any, pathParts: string[], value: any): void {
    let current = obj;

    for (let i = 0; i < pathParts.length - 1; i++) {
      const part = pathParts[i];
      const isArrayIndex = /^\d+$/.test(pathParts[i + 1]);

      if (!(part in current)) {
        current[part] = isArrayIndex ? [] : {};
      }
      current = current[part];
    }

    const lastPart = pathParts[pathParts.length - 1];
    current[lastPart] = value;
  }

  private getNestedValue(obj: any, pathParts: string[]): any {
    let current = obj;

    for (const part of pathParts) {
      if (current && typeof current === 'object' && part in current) {
        current = current[part];
      } else {
        return undefined;
      }
    }

    return current;
  }

  private removeNestedValue(obj: any, pathParts: string[]): void {
    if (pathParts.length === 0) return;

    let current = obj;

    for (let i = 0; i < pathParts.length - 1; i++) {
      const part = pathParts[i];
      if (!(part in current)) return;
      current = current[part];
    }

    const lastPart = pathParts[pathParts.length - 1];
    if (Array.isArray(current)) {
      current.splice(parseInt(lastPart), 1);
    } else {
      delete current[lastPart];
    }
  }
}

// =============================
// ===== Utility functions =====
// =============================

// Factory functions for creating builders
export function createScenario(name: string): ScenarioDefinitionBuilder {
  const builder = new ScenarioBuilder();
  builder.setName(name);
  return builder;
}

// Utility function to convert scenario to PromptRequest
function scenarioToPromptRequest(scenario: Partial<Scenario>, messages?: AllMessage[]): PromptRequest {
  // Get platform config from SDK configuration
  const sdkConfig = getSDKConfig();
  const platformConfig = sdkConfig.getPlatformConfig();

  // Convert scenario prompt string to a user message
  const finalMessages: AllMessage[] = messages
    ? messages
    : [
        {
          role: 'user' as const,
          content: [{ text: scenario.prompt || '' }],
        },
      ];

  // Map context parameters to prompt parameters
  const promptRequest: PromptRequest = {
    platform_config_raw: platformConfig,
    prompt: {
      system_instruction: scenario.context?.system_instruction || undefined,
      messages: finalMessages,
      tools: scenario.tools || [],
      tool_choice: 'auto' as const,
      temperature: scenario.context?.temperature || undefined,
      seed: scenario.context?.seed || undefined,
      max_output_tokens: scenario.context?.max_output_tokens || undefined,
      stop_sequences: scenario.context?.stop_sequences || undefined,
      top_p: scenario.context?.top_p || undefined,
    },
  };

  return promptRequest;
}

// Validation functions
export function validateScenario(scenario: unknown): scenario is Scenario {
  try {
    ScenarioSchema.parse(scenario);
    return true;
  } catch {
    return false;
  }
}

// Validation context
export function validateContext(context: unknown): context is Context {
  try {
    ContextSchema.parse(context);
    return true;
  } catch {
    return false;
  }
}

// Utility functions for working with scenarios
export function cloneScenario(scenario: Scenario): ScenarioDefinitionBuilder {
  const builder = createScenario(scenario.name);

  builder.setPrompt(scenario.prompt);

  if (scenario.context) {
    builder.setContext(scenario.context);
  }

  if (scenario.tools && scenario.tools.length > 0) {
    for (const tool of scenario.tools) {
      builder.addTool(tool);
    }
  }

  return builder;
}

export function mergeContexts(baseContext: Context, overrideContext: Partial<Context>): Context {
  return ContextSchema.parse({
    ...baseContext,
    ...overrideContext,
  });
}

export function getScenarioSummary(scenario: Scenario): {
  name: string;
  prompt: string;
  toolCount: number;
  hasSystemInstruction: boolean;
  temperature?: number;
  maxOutputTokens?: number;
  verbose?: boolean;
} {
  return {
    name: scenario.name,
    prompt: scenario.prompt,
    toolCount: scenario.tools.length,
    hasSystemInstruction: !!scenario.context.system_instruction,
    temperature: scenario.context.temperature || undefined,
    maxOutputTokens: scenario.context.max_output_tokens || undefined,
    verbose: scenario.verbose || undefined,
  };
}

// Export types for external use
export type { ScenarioDefinitionBuilder };
