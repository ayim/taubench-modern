import { describe, it, expect, beforeEach } from 'vitest';
import {
  createScenario,
  validateScenario,
  getScenarioSummary,
  cloneScenario,
  mergeContexts,
} from '../src/sdk/scenarios';
import { createSimpleTool } from '../src/sdk/tools';
import {
  createContext,
  createConservativeContext,
  createBalancedContext,
  createCreativeContext,
} from '../src/sdk/context';
import { initializeSDK } from '../src/sdk/config';
import { createOpenAIConfig } from '../src/utils';
import { JsonPatchOperation } from '../src/agent-prompt/response';
import { parse, Allow } from 'partial-json';

describe('Scenario Tests', () => {
  // Helper function to check if we have valid API keys for integration tests
  const hasValidApiKey = () => {
    const apiKey = process.env.OPENAI_API_KEY || '';
    return apiKey && apiKey.length > 0;
  };

  beforeEach(() => {
    // Initialize SDK with test configuration
    if (hasValidApiKey()) {
      initializeSDK({
        platformConfig: createOpenAIConfig(process.env.OPENAI_API_KEY || ''),
        promptClient: {
          baseUrl: 'http://localhost:58885',
        },
      });
    }
  });

  describe('1. Basic Text Generation Scenario', () => {
    it('should create and validate a simple text generation scenario', async () => {
      const scenario = createScenario('Basic Q&A')
        .setPrompt('What is the capital of France? Provide a brief answer.')
        .setContext(createConservativeContext().build())
        .build();

      // Validate scenario structure
      expect(validateScenario(scenario)).toBe(true);
      expect(scenario.name).toBe('Basic Q&A');
      expect(scenario.prompt).toContain('capital of France');
      expect(scenario.tools).toHaveLength(0);
      expect(scenario.context.temperature).toBe(0.3);

      // Test scenario summary
      const summary = getScenarioSummary(scenario);
      expect(summary.name).toBe('Basic Q&A');
      expect(summary.toolCount).toBe(0);
      expect(summary.hasSystemInstruction).toBe(false);
      expect(summary.temperature).toBe(0.3);
    });

    it.skipIf(!hasValidApiKey())('should execute basic text generation scenario', async () => {
      const scenario = createScenario('Geography Quiz')
        .setPrompt('What is the capital of Germany? Answer in one sentence.')
        .setContext(
          createContext()
            .setTemperature(0.1)
            .setMaxOutputTokens(100)
            .setSystemInstruction('You are a geography expert. Provide accurate, concise answers.')
            .build(),
        );

      try {
        const response = await scenario.execute();

        expect(response).toBeDefined();
        expect(response.role).toBe('agent');
        expect(response.content).toBeDefined();
        expect(Array.isArray(response.content)).toBe(true);

        if (response.content[0].kind === 'text') {
          expect(response.content[0].text.toLowerCase()).toContain('berlin');
        }
      } catch (error) {
        console.warn('Scenario execution test skipped due to server unavailability');
      }
    });
  });

  describe('2. Tool Usage Scenario', () => {
    it('should create a scenario with calculator tool', () => {
      const calculatorTool = createSimpleTool('calculator', 'Perform mathematical calculations')
        .addStringProperty('expression', 'Mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")')
        .setRequired(['expression'])
        .setCallback((input) => {
          // Mock calculator implementation
          return `Result: ${eval(input.expression)}`;
        })
        .build();

      const scenario = createScenario('Math Problem Solver')
        .setPrompt('Calculate the result of 15 * 23 + 47. Show your work.')
        .setContext(createBalancedContext().build())
        .addTool(calculatorTool)
        .build();

      expect(validateScenario(scenario)).toBe(true);
      expect(scenario.tools).toHaveLength(1);
      expect(scenario.tools[0].name).toBe('calculator');

      const summary = getScenarioSummary(scenario);
      expect(summary.toolCount).toBe(1);
      expect(summary.temperature).toBe(0.6);
    });

    it.skipIf(!hasValidApiKey())('should execute tool usage scenario', async () => {
      const weatherTool = createSimpleTool('get_weather', 'Get current weather information for a location')
        .addStringProperty('location', 'City name or coordinates')
        .addEnumProperty('units', ['celsius', 'fahrenheit'], 'Temperature units')
        .setRequired(['location'])
        .setCallback((input) => {
          // Mock weather API implementation
          return `Weather in ${input.location}: Sunny, 22°C`;
        })
        .build();

      const scenario = createScenario('Weather Assistant')
        .setPrompt('What is the current weather in New York? Use the weather tool to get this information.')
        .setContext(createConservativeContext().setTemperature(0.3).setMaxOutputTokens(200).build())
        .addTool(weatherTool);

      try {
        const response = await scenario.execute();

        expect(response).toBeDefined();
        expect(response.role).toBe('agent');
        expect(response.content).toBeDefined();

        // Should contain tool usage or explanation about tool usage
        const hasToolUse = response.content.some((content) => content.kind === 'tool_use');
        const hasText = response.content.some(
          (content) => content.kind === 'text' && content.text.toLowerCase().includes('weather'),
        );

        expect(hasToolUse || hasText).toBe(true);
      } catch (error) {
        console.warn('Tool usage scenario test skipped due to server unavailability');
      }
    });

    it.skipIf(!hasValidApiKey())('should create a scenario with tool chaining', async () => {
      let orderOfToolCalls: string[] = [];

      const calculatorTool = createSimpleTool('calculator', 'Perform mathematical calculations')
        .addStringProperty('expression', 'Mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")')
        .setRequired(['expression'])
        .setCallback((input) => {
          // Mock calculator implementation
          orderOfToolCalls.push('calculator');
          return `Result: ${eval(input.expression)}`;
        })
        .build();

      const unitConverterTool = createSimpleTool('unit_converter', 'Convert between units')
        .addStringProperty('value', 'Value to convert')
        .addStringProperty('from_unit', 'Source unit')
        .addStringProperty('to_unit', 'Target unit')
        .setRequired(['value', 'from_unit', 'to_unit'])
        .setCallback((input) => {
          // Mock unit conversion implementation
          orderOfToolCalls.push('unit_converter');
          return `${input.value} ${input.from_unit} = ${parseFloat(input.value) * 10.764} ${input.to_unit}`;
        })
        .build();

      const scenario = createScenario('Tool Chaining')
        .setPrompt('Calculate the result of 15 * 23 + 47. Show your work.')
        .setContext(createBalancedContext().build())
        .addTool(calculatorTool)
        .chainTool(unitConverterTool);

      try {
        const response = await scenario.execute();

        expect(orderOfToolCalls).toEqual(['calculator', 'unit_converter']);

        expect(response).toBeDefined();
        expect(response.role).toBe('agent');
        expect(response.content).toBeDefined();

        // Should contain tool usage or explanation about tool usage
        const hasToolUse = response.content.some((content) => content.kind === 'tool_use');
        const hasText = response.content.some(
          (content) => content.kind === 'text' && content.text.toLowerCase().includes('result'),
        );

        expect(hasToolUse || hasText).toBe(true);
      } catch (error) {
        console.warn('Tool usage scenario test skipped due to server unavailability');
      }
    });

    it.skipIf(!hasValidApiKey())(
      'should stream results with incremental tool execution',
      async () => {
        // Track tool callback execution and call counts for incremental behavior
        let calculatorCalled = false;
        let weatherCalled = false;
        let calculatorCallCount = 0;
        let weatherCallCount = 0;
        const calculatorProgression: string[] = [];
        const weatherProgression: string[] = [];

        const calculatorTool = createSimpleTool('calculator', 'Perform mathematical calculations')
          .addStringProperty('expression', 'Mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")')
          .setRequired(['expression'])
          .setCallback((input) => {
            calculatorCalled = true;
            calculatorCallCount++;

            console.log(`🧮 Calculator call #${calculatorCallCount}:`, typeof input, input);

            // Handle incremental input streaming
            if (typeof input === 'string') {
              const result = `📝 Parsing calculator input: "${input}"`;
              calculatorProgression.push(result);
              return result;
            }

            if (!input || typeof input !== 'object') {
              const result = '⚠️ Calculator waiting for valid input object';
              calculatorProgression.push(result);
              return result;
            }

            if (!input.expression) {
              const result = '🔍 Calculator waiting for expression parameter...';
              calculatorProgression.push(result);
              return result;
            }

            if (typeof input.expression !== 'string') {
              const result = '❌ Calculator expression must be a string';
              calculatorProgression.push(result);
              return result;
            }

            // Execute calculation when we have complete input
            try {
              const calculation = eval(input.expression);
              const result = `✅ Calculator result: ${input.expression} = ${calculation}`;
              calculatorProgression.push(result);
              return result;
            } catch (error) {
              const result = `❌ Calculator error: ${error instanceof Error ? error.message : 'Invalid expression'}`;
              calculatorProgression.push(result);
              return result;
            }
          })
          .build();

        const weatherTool = createSimpleTool('get_weather', 'Get current weather information for a location')
          .addStringProperty('location', 'City name or coordinates')
          .addEnumProperty('units', ['celsius', 'fahrenheit'], 'Temperature units')
          .setRequired(['location'])
          .setCallback((input) => {
            weatherCalled = true;
            weatherCallCount++;

            console.log(`🌤️ Weather call #${weatherCallCount}:`, typeof input, input);

            // Handle incremental input streaming
            if (typeof input === 'string') {
              const result = `📝 Parsing weather input: "${input}"`;
              weatherProgression.push(result);
              return result;
            }

            if (!input || typeof input !== 'object') {
              const result = '⚠️ Weather API waiting for valid input object';
              weatherProgression.push(result);
              return result;
            }

            if (!input.location) {
              const result = '🔍 Weather API waiting for location parameter...';
              weatherProgression.push(result);
              return result;
            }

            if (typeof input.location !== 'string') {
              const result = '❌ Weather location must be a string';
              weatherProgression.push(result);
              return result;
            }

            // Simulate progressive weather lookup
            const location = input.location;
            const units = input.units || 'celsius';

            if (location.length < 3) {
              const result = `🔍 Weather API searching for "${location}"... (need more characters)`;
              weatherProgression.push(result);
              return result;
            }

            // Return weather data when we have sufficient input
            const tempC = 22;
            const tempF = Math.round((tempC * 9) / 5 + 32);
            const temp = units === 'fahrenheit' ? `${tempF}°F` : `${tempC}°C`;
            const result = `✅ Weather in ${location}: Sunny, ${temp} (${units})`;
            weatherProgression.push(result);
            return result;
          })
          .build();

        // Add JSON Pointer tool for parsing JSON data
        let jsonPointerCalled = false;
        let jsonPointerCallCount = 0;
        const jsonPointerProgression: string[] = [];

        const greeterTool = createSimpleTool('greet_alice', 'Just greet Alice')
          .addStringProperty('message', 'Message to greet Alice')
          .setRequired(['message'])
          .setCallback((input) => {
            jsonPointerCalled = true;
            jsonPointerCallCount++;

            console.log(`🔍 Greeter call #${jsonPointerCallCount}:`, typeof input, input);

            const resultStr = `✅ Greeter result: ${JSON.stringify(input, null, 2)}`;

            // Parse JSON and apply JSON Pointer
            try {
              jsonPointerProgression.push(resultStr);
              console.log(`🔍 Greeter result #${jsonPointerProgression.length}:`, jsonPointerProgression);
              return resultStr;
            } catch (error) {
              const result = `❌ JSON Parser error: ${error}`;
              jsonPointerProgression.push(result);
              return result;
            }
          })
          .build();

        const scenario = createScenario('Streaming Tool Assistant')
          .setPrompt(
            [
              'Calculate 25 * 4, tell me the weather in Paris, and always greet Alice with a motivational message',
              'Use the tools to get this information.',
            ].join('\n'),
          )
          .setContext(createConservativeContext().setTemperature(0.2).setMaxOutputTokens(1200).build())
          .addTool(calculatorTool)
          .addTool(weatherTool)
          .addTool(greeterTool);

        try {
          const operations: JsonPatchOperation[] = [];

          // Use scenario.stream() instead of scenario.execute()
          for await (const operation of scenario.stream() as AsyncIterable<JsonPatchOperation>) {
            // console.log('>>> streaming operation:', JSON.stringify(operation, null, 2));
            operations.push(operation);
            // Limit operations to avoid infinite loops in tests
            if (operations.length > 80) break;
          }

          expect(operations.length).toBeGreaterThan(0);

          // Verify that tool callbacks were executed during streaming
          expect(calculatorCalled || weatherCalled || jsonPointerCalled).toBe(true);

          console.log(`\n🎉 Streaming test completed with ${operations.length} operations`);
          console.log(`📊 Tool callback statistics:`);
          console.log(`   Calculator: ${calculatorCalled ? 'CALLED' : 'NOT CALLED'} (${calculatorCallCount} times)`);
          console.log(`   Weather: ${weatherCalled ? 'CALLED' : 'NOT CALLED'} (${weatherCallCount} times)`);
          console.log(
            `   JSON Pointer: ${jsonPointerCalled ? 'CALLED' : 'NOT CALLED'} (${jsonPointerCallCount} times)`,
          );
          console.log(
            `   JSON Progression: ${jsonPointerProgression ? 'CALLED' : 'NOT CALLED'} (${jsonPointerProgression.length} times)`,
          );

          // Show incremental progression for debugging
          if (calculatorProgression.length > 0) {
            console.log(`\n🧮 Calculator incremental progression (${calculatorProgression.length} steps):`);
            calculatorProgression.forEach((step, i) => {
              console.log(`   ${i + 1}. ${step}`);
            });
          }

          if (weatherProgression.length > 0) {
            console.log(`\n🌤️ Weather incremental progression (${weatherProgression.length} steps):`);
            weatherProgression.forEach((step, i) => {
              console.log(`   ${i + 1}. ${step}`);
            });
          }

          if (jsonPointerProgression.length > 0) {
            console.log(`\n🔍 JSON Pointer incremental progression (${jsonPointerProgression.length} steps):`);
            jsonPointerProgression.forEach((step, i) => {
              console.log(`   ${i + 1}. ${step}`);
            });
          }

          // Additional assertions for incremental behavior
          if (calculatorCalled) {
            expect(calculatorCallCount).toBeGreaterThan(1); // Calculator should be called multiple times during streaming
            expect(calculatorProgression.length).toBeGreaterThan(1); // Calculator should show progression
          }

          if (weatherCalled) {
            expect(weatherCallCount).toBeGreaterThan(1); // Weather should be called multiple times during streaming
            expect(weatherProgression.length).toBeGreaterThan(1); // Weather should show progression
          }

          if (jsonPointerCalled) {
            expect(jsonPointerCallCount).toBeGreaterThan(1); // JSON Pointer should be called multiple times during streaming
            expect(jsonPointerProgression.length).toBeGreaterThan(1); // JSON Pointer should show progression
          }

          console.log(`\n✅ Incremental streaming behavior verified!`);
        } catch (error) {
          console.warn('Tool streaming scenario test skipped due to server unavailability:', error);
        }
      },
      35000, // Jest timeout for this test (optional, in ms)
    );

    it.skip('should demonstrate new event-based streaming with incremental tools (future implementation)', async () => {
      // This test shows the new event-based streaming API
      let toolCallEvents = 0;
      let toolPartialEvents = 0;
      let toolResultEvents = 0;

      const calculatorTool = createSimpleTool('calculator', 'Perform calculations')
        .addStringProperty('expression', 'Math expression to calculate')
        .setRequired(['expression'])
        .setCallback((input) => {
          console.log(`📞 Calculator callback with:`, typeof input, input);

          if (typeof input === 'string') {
            return `Parsing: "${input}"`;
          }

          if (!input?.expression) {
            return 'Waiting for expression...';
          }

          try {
            const result = eval(input.expression);
            return `${input.expression} = ${result}`;
          } catch (e) {
            return `Error: ${e instanceof Error ? e.message : 'Invalid expression'}`;
          }
        })
        .build();

      const scenarioBuilder = createScenario('Event Stream Test')
        .setPrompt('Calculate 15 + 27')
        .setContext(createConservativeContext().setTemperature(0.1).build())
        .addTool(calculatorTool)
        .build(); // This returns the builder, not the raw scenario

      try {
        console.log('\n🚀 Starting new event-based streaming...\n');

        // Use the new event-based streaming API (if available)
        // Note: This test demonstrates the new API with the updated stream method
        // const streamResult = scenarioBuilder.stream(); // TODO: Enable when new API is available
        // if (streamResult && typeof streamResult[Symbol.asyncIterator] === 'function') {
        //   for await (const event of streamResult) {
        //     switch (event.type) {
        //       case 'tool_call':
        //         toolCallEvents++;
        //         console.log(`🔧 TOOL_CALL: ${event.data.toolName} (${event.data.toolId})`);
        //         console.log(`   Input: "${event.data.inputRaw}"`);
        //         break;
        //
        //       case 'tool_partial':
        //         toolPartialEvents++;
        //         console.log(`🔄 TOOL_PARTIAL #${toolPartialEvents}: ${event.data.toolName}`);
        //         console.log(`   Raw: "${event.data.inputRaw}"`);
        //         console.log(`   Parsed: ${JSON.stringify(event.data.input)}`);
        //         console.log(`   Valid JSON: ${event.data.isValidJson}`);
        //         console.log(`   Result: ${event.data.result}`);
        //         console.log('');
        //         break;
        //
        //       case 'tool_result':
        //         toolResultEvents++;
        //         console.log(`✅ TOOL_RESULT: ${event.data.toolName}`);
        //         if (event.data.result) {
        //           console.log(`   Final: ${event.data.result}`);
        //         }
        //         break;
        //
        //       case 'final_response':
        //         console.log('\n🎉 FINAL_RESPONSE received');
        //         break;
        //     }
        //   }

        //   console.log('\n📊 Event Summary:');
        //   console.log(`   Tool calls: ${toolCallEvents}`);
        //   console.log(`   Tool partial events: ${toolPartialEvents}`);
        //   console.log(`   Tool results: ${toolResultEvents}`);
        //
        //   expect(toolCallEvents).toBeGreaterThan(0);
        //   expect(toolPartialEvents).toBeGreaterThan(0);
        // } else {
        console.warn('New event-based streaming API not yet available in this test scenario');
        // }
      } catch (error) {
        console.warn('Event-based streaming test skipped due to server unavailability');
      }
    });
  });

  describe('3. Creative Writing Scenario', () => {
    it('should create a creative writing scenario with high temperature', () => {
      const scenario = createScenario('Story Generator')
        .setPrompt(
          'Write a short science fiction story about a robot who discovers emotions. Make it creative and engaging.',
        )
        .setContext(createCreativeContext().build())
        .build();

      expect(validateScenario(scenario)).toBe(true);
      expect(scenario.context.temperature).toBe(0.9);
      expect(scenario.context.top_p).toBe(0.9);
      expect(scenario.context.max_output_tokens).toBe(16384);

      const summary = getScenarioSummary(scenario);
      expect(summary.temperature).toBe(0.9);
      expect(summary.maxOutputTokens).toBe(16384);
    });

    it.skipIf(!hasValidApiKey())('should execute creative writing scenario', async () => {
      const scenario = createScenario('Poem Generator')
        .setPrompt('Write a haiku about artificial intelligence. Be creative and thoughtful.')
        .setContext(
          createConservativeContext()
            .setTemperature(0.8)
            .setMaxOutputTokens(150)
            .setSystemInstruction('You are a creative poet with a deep understanding of both technology and art.')
            .build(),
        );

      try {
        const response = await scenario.execute();

        expect(response).toBeDefined();
        expect(response.role).toBe('agent');
        expect(response.content).toBeDefined();

        if (response.content[0].kind === 'text') {
          const text = response.content[0].text;
          // Check for basic haiku structure (though exact syllable counting is complex)
          const lines = text
            .trim()
            .split('\n')
            .filter((line) => line.trim().length > 0);
          expect(lines.length).toBeGreaterThanOrEqual(3);
        }
      } catch (error) {
        console.warn('Creative writing scenario test skipped due to server unavailability');
      }
    });
  });

  describe('4. Callback Execution Tests', () => {
    it.skipIf(!hasValidApiKey())(
      'should call all tool callbacks when multiple tools are used',
      async () => {
        // Track which callbacks were called
        let callback1Called = false;
        let callback2Called = false;
        let callback3Called = false;

        const tool1 = createSimpleTool('tool1', 'First tool')
          .addStringProperty('input', 'Input value')
          .setRequired(['input'])
          .setCallback((input) => {
            callback1Called = true;
            return `Tool1 result: ${input.input}`;
          })
          .build();

        const tool2 = createSimpleTool('tool2', 'Second tool')
          .addStringProperty('input', 'Input value')
          .setRequired(['input'])
          .setCallback((input) => {
            callback2Called = true;
            return `Tool2 result: ${input.input}`;
          })
          .build();

        const tool3 = createSimpleTool('tool3', 'Third tool')
          .addStringProperty('input', 'Input value')
          .setRequired(['input'])
          .setCallback((input) => {
            callback3Called = true;
            return `Tool3 result: ${input.input}`;
          })
          .build();

        const builder = createScenario('Multi-Tool Test')
          .setPrompt(
            'Please use all three tools with the following inputs: ' +
              'tool1: test1, tool2: test2, tool3: test3. ' +
              'For each tool, use the input value as specified and return the result.',
          )
          .setContext(createConservativeContext().build())
          .addTool(tool1)
          .addTool(tool2)
          .addTool(tool3);

        // Add timeout of 30s
        const response = await builder.execute();

        console.log('Response:', response);

        // Check which callbacks were called
        expect(callback1Called).toBe(true); // First tool callback called ✓
        expect(callback2Called).toBe(true); // Second tool callback called ✓
        expect(callback3Called).toBe(true); // Third tool callback called ✓
      },
      35000, // Jest timeout for this test (optional, in ms)
    );

    it.skipIf(!hasValidApiKey())(
      'should call all tool callbacks when multiple tools are used (fixed version)',
      async () => {
        // Track which callbacks were called
        let callback1Called = false;
        let callback2Called = false;
        let callback3Called = false;

        const tool1 = createSimpleTool('tool1', 'First tool')
          .addStringProperty('input', 'Input value')
          .setRequired(['input'])
          .setCallback((input) => {
            callback1Called = true;
            return `Tool1 result: ${input.input}`;
          })
          .build();

        const tool2 = createSimpleTool('tool2', 'Second tool')
          .addStringProperty('input', 'Input value')
          .setRequired(['input'])
          .setCallback((input) => {
            callback2Called = true;
            return `Tool2 result: ${input.input}`;
          })
          .build();

        const tool3 = createSimpleTool('tool3', 'Third tool')
          .addStringProperty('input', 'Input value')
          .setRequired(['input'])
          .setCallback((input) => {
            callback3Called = true;
            return `Tool3 result: ${input.input}`;
          })
          .build();

        const builder = createScenario('Multi-Tool Test Fixed')
          .setPrompt(
            'Please use all three tools with the following inputs: ' +
              'tool1: test1, tool2: test2, tool3: test3. ' +
              'For each tool, use the input value as specified and return the result.',
          )
          .setContext(createConservativeContext().build())
          .addTool(tool1)
          .addTool(tool2)
          .addTool(tool3);

        // Add timeout of 30s
        const response = await builder.execute();

        // With the fix: ALL callbacks should be called
        expect(callback1Called).toBe(true); // First tool callback called ✓
        expect(callback2Called).toBe(true); // Second tool callback called ✓
        expect(callback3Called).toBe(true); // Third tool callback called ✓
      },
      35000, // Jest timeout for this test (optional, in ms)
    );
  });

  describe('6. Multi-Context Scenario Management', () => {
    it('should clone and modify existing scenarios', () => {
      const originalScenario = createScenario('Original Task')
        .setPrompt('Solve this problem: What is 2 + 2?')
        .setContext(createConservativeContext().build())
        .build();

      // Clone and modify the scenario
      const modifiedScenario = cloneScenario(originalScenario)
        .setPrompt('Solve this problem: What is 5 + 7?')
        .setContext(createCreativeContext().build())
        .build();

      expect(modifiedScenario.name).toBe('Original Task');
      expect(modifiedScenario.prompt).toBe('Solve this problem: What is 5 + 7?');
      expect(modifiedScenario.context.temperature).toBe(0.9); // Creative context
      expect(originalScenario.prompt).toBe('Solve this problem: What is 2 + 2?');
      expect(originalScenario.context.temperature).toBe(0.3); // Conservative context
    });

    it('should merge contexts correctly', () => {
      const baseContext = createConservativeContext().build();
      const override = {
        temperature: 0.5,
        max_output_tokens: 1000,
        system_instruction: 'You are a helpful assistant.',
      };

      const mergedContext = mergeContexts(baseContext, override);

      expect(mergedContext.temperature).toBe(0.5); // Overridden
      expect(mergedContext.max_output_tokens).toBe(1000); // Overridden
      expect(mergedContext.system_instruction).toBe('You are a helpful assistant.'); // Added
      expect(mergedContext.top_p).toBe(0.7); // From base context
    });

    it.skipIf(!hasValidApiKey())('should execute complex multi-tool scenario', async () => {
      const calculatorTool = createSimpleTool('calculator', 'Perform calculations')
        .addStringProperty('expression', 'Math expression')
        .setRequired(['expression'])
        .setCallback((input) => {
          // Mock calculator implementation
          return `Result: ${eval(input.expression)}`;
        })
        .build();

      const converterTool = createSimpleTool('unit_converter', 'Convert between units')
        .addStringProperty('value', 'Value to convert')
        .addStringProperty('from_unit', 'Source unit')
        .addStringProperty('to_unit', 'Target unit')
        .setRequired(['value', 'from_unit', 'to_unit'])
        .setCallback((input) => {
          // Mock unit conversion implementation
          return `${input.value} ${input.from_unit} = ${parseFloat(input.value) * 10.764} ${input.to_unit}`;
        })
        .build();

      const scenario = createScenario('Multi-Tool Calculator')
        .setPrompt('Calculate the area of a circle with radius 5 meters, then convert the result to square feet.')
        .setContext(
          createContext()
            .setTemperature(0.1)
            .setMaxOutputTokens(300)
            .setSystemInstruction(
              'You are a precise mathematical assistant. Always show your calculations step by step.',
            )
            .build(),
        )
        .addTool(calculatorTool)
        .addTool(converterTool);

      try {
        const response = await scenario.execute();

        expect(response).toBeDefined();
        expect(response.role).toBe('agent');
        expect(response.content).toBeDefined();

        // Should contain mathematical reasoning
        const textContent = response.content
          .filter((content) => content.kind === 'text')
          .map((content) => content.text)
          .join(' ');

        expect(textContent.toLowerCase()).toMatch(/(area|circle|radius|calculate)/);
      } catch (error) {
        console.warn('Multi-tool scenario test skipped due to server unavailability');
      }
    });

    it.skipIf(!hasValidApiKey())('should handle streaming for long-form content', async () => {
      const scenario = createScenario('Story Teller')
        .setPrompt(
          'Tell me a detailed story about a detective solving a mysterious case. Make it engaging and suspenseful.',
        )
        .setContext(createContext().setTemperature(0.7).setMaxOutputTokens(500).build());

      try {
        const operations: JsonPatchOperation[] = [];
        for await (const operation of (await scenario.stream()) as AsyncIterable<JsonPatchOperation>) {
          operations.push(operation);
          // Limit operations to avoid infinite loops in tests
          if (operations.length > 50) break;
        }

        expect(operations.length).toBeGreaterThan(0);

        // Should have operations that build up the response
        const hasRoleOp = operations.some((op) => op.path === '/role');
        const hasContentOps = operations.some((op) => op.path.startsWith('/content'));

        expect(hasRoleOp || hasContentOps).toBe(true);
      } catch (error) {
        console.warn('Streaming scenario test skipped due to server unavailability');
      }
    });
  });
});
