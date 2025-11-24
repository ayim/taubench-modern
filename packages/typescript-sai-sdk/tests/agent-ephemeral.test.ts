/**
 * Tests for ephemeral agent streaming functionality
 */
import { describe, it, expect, beforeEach } from 'vitest';

import {
  EphemeralAgentClient,
  createEphemeralAgentClient,
  createBasicAgentConfig,
  createHumanThreadMessage,
  ThreadMessage,
  createSaiGenericAgentConfig,
} from '../src/agent-ephemeral/index';
import { createOpenAIConfig } from '../src/utils';

describe('EphemeralAgentClient', () => {
  let client: EphemeralAgentClient;

  // Helper function to check if we have valid API keys for integration tests
  const hasValidApiKey = () => {
    const apiKey = process.env.OPENAI_API_KEY || '';
    // Check for a real OpenAI API key format (starts with sk- and has reasonable length)
    return apiKey && apiKey.startsWith('sk-');
  };

  beforeEach(() => {
    client = createEphemeralAgentClient({
      baseUrl: 'ws://localhost:58885',
      timeout: 30000,
    });
  });

  describe('Test Creating Streams', () => {
    // ===============================
    // INTERNAL TESTS
    // ===============================
    it.skipIf(!hasValidApiKey())(
      'should create a stream successfully',
      async () => {
        const agentConfig = createBasicAgentConfig({
          name: 'test-agent-' + Date.now().toString(),
          description: 'Test agent for integration testing',
          runbook: 'You are a helpful assistant. Respond with "Hello from ephemeral agent!"',
          platform_configs: [createOpenAIConfig(process.env.OPENAI_API_KEY || '')],
        });

        return new Promise<void>(async (resolve, reject) => {
          const timeoutId = setTimeout(() => {
            reject(new Error('Test timeout after 30 seconds'));
          }, 30000);

          const stream = await client.createStream({
            agent: agentConfig,
            messages: [createHumanThreadMessage('Hello. What can you do?')],
            handlers: {
              onAgentReady: (event) => {
                console.log('[TEST] Agent ready:', JSON.stringify(event, null, 2));
                expect(event.run_id).toBeDefined();
                expect(event.thread_id).toBeDefined();
                expect(event.agent_id).toBeDefined();
                expect(event.timestamp).toBeDefined();
              },
              onMessage: (event) => {
                console.log('[TEST] Message received:', JSON.stringify(event, null, 2));
              },
              onMessageEnd: (event) => {
                console.log('[TEST] Message end:', JSON.stringify(event, null, 2));
                expect(event.message_id).toBeDefined();
                expect(event.thread_id).toBeDefined();
                expect(event.agent_id).toBeDefined();
                expect(event.timestamp).toBeDefined();
                expect(event.event_type).toBe('message_end');
                expect(event.complete).toBeDefined();
                expect(event.data?.content).toBeDefined();
                expect(event.data?.content[1].text).toBe('Hello from ephemeral agent!');
              },
              onAgentFinished: (event) => {
                console.log('[TEST] Agent finished!', JSON.stringify(event, null, 2));
                clearTimeout(timeoutId);
                resolve();
              },
              onClose: (code, reason) => {
                console.log('[TEST] Connection closed:', code, reason);
                clearTimeout(timeoutId);
                resolve();
              },
              onAgentError: (event) => {
                console.error('[TEST] Agent error:', event);
                clearTimeout(timeoutId);
                reject(new Error(`Agent error: ${event}`));
              },
              onEvent: (event) => {
                // console.log('[TEST] Event:', event);
              },
            },
          });

          if (!stream) {
            clearTimeout(timeoutId);
            reject(new Error('Failed to create stream'));
          }
        });
      },
      45000,
    ); // 45 second timeout for this test

    it.skipIf(!hasValidApiKey()).skip(
      'should keep a conversation going with multiple messages',
      async () => {
        const agentConfig = createBasicAgentConfig({
          name: 'test-agent-' + Date.now().toString(),
          description: 'Test agent for integration testing',
          runbook: [
            'You are a helpful assistant.',
            'When someone says "message 1", respond with "1 response received".',
            'When someone says "message 2", respond with "2 response received".',
            'When someone says "message 3", respond with "3 response received".',
          ].join('\n'),
          platform_configs: [createOpenAIConfig(process.env.OPENAI_API_KEY || '')],
        });

        return new Promise<void>(async (resolve, reject) => {
          const timeoutId = setTimeout(() => {
            reject(new Error('Test timeout after 60 seconds'));
          }, 60000);
          const messages: ThreadMessage[] = [];

          for (let i = 0; i < 3; i++) {
            console.warn('[TEST] Adding human message:', `message ${i + 1}`);
            // Add human message to messages
            messages.push(createHumanThreadMessage(`message ${i + 1}`));
            console.warn('[TEST] Messages', messages);

            // Wait for message to be added to messages
            await new Promise<void>(async (resolveWaitMsg) => {
              // Create stream
              const stream = await client.createStream({
                agent: agentConfig,
                messages,
                handlers: {
                  onAgentReady: (event) => {
                    expect(event.run_id).toBeDefined();
                    expect(event.thread_id).toBeDefined();
                    expect(event.agent_id).toBeDefined();
                    expect(event.timestamp).toBeDefined();
                  },
                  onMessage: (event) => {
                    // console.log('[TEST] Message received:', JSON.stringify(event, null, 2));
                  },
                  onMessageEnd: (event) => {
                    console.log('[TEST] Message end:', JSON.stringify(event, null, 2));
                    expect(event.message_id).toBeDefined();
                    expect(event.thread_id).toBeDefined();
                    expect(event.agent_id).toBeDefined();
                    expect(event.timestamp).toBeDefined();
                    expect(event.event_type).toBe('message_end');
                    expect(event.data?.content).toBeDefined();
                    expect(event.data?.content[1].text).toContain(`${i + 1} response received`);

                    // Add agent message to messages
                    messages.push(event.data as ThreadMessage);

                    // Wait for message DONE
                    console.warn('[TEST] Message VALIDATED!');
                    resolveWaitMsg();
                  },
                  onAgentFinished: (event) => {
                    console.log('[TEST] Agent finished!', JSON.stringify(event, null, 2));
                    resolveWaitMsg();
                  },
                  onClose: (code, reason) => {
                    console.log('[TEST] Connection closed:', code, reason);
                    clearTimeout(timeoutId);
                    resolveWaitMsg();
                  },
                  onAgentError: (event) => {
                    console.error('[TEST] Agent error:', event);
                    clearTimeout(timeoutId);
                    reject(new Error(`Agent error: ${event}`));
                    resolveWaitMsg();
                  },
                  onEvent: (event) => {
                    // console.log('[TEST] Event:', event);
                  },
                },
              });

              if (!stream) {
                clearTimeout(timeoutId);
                reject(new Error('Failed to create stream'));
                return;
              }
            });
          }

          clearTimeout(timeoutId);
          resolve();
        });
      },
      60000,
    ); // 60 second timeout for this test

    // ===============================
    // EXTERNAL TESTS
    // ===============================
    it.skipIf(hasValidApiKey())('should show helpful message when integration tests are skipped', async () => {
      // This test runs when we don't have valid API keys or are in CI
      console.log('\n🚀 Integration Test Requirements:');
      console.log('   1. Start the agent server: npm run dev (in main project)');
      console.log('   2. Set OPENAI_API_KEY environment variable to a real OpenAI API key (starts with sk-)');
      console.log('   3. Ensure not running in CI (or set CI=false)');
      console.log('   4. Run tests: npm test');
      console.log('   📍 Agent server should be running on ws://localhost:58885\n');

      const currentKey = process.env.OPENAI_API_KEY || '';
      if (currentKey && !currentKey.startsWith('sk-')) {
        console.log('   ⚠️  Current OPENAI_API_KEY appears to be a test key, not a real OpenAI API key\n');
      }

      expect(true).toBe(true); // This test always passes, it's just informational
    });

    it('should handle validation errors', async () => {
      // Test with completely invalid agent configuration that should fail validation
      const invalidConfig = {
        name: '', // Empty name should fail validation
        description: 'Test agent',
        runbook: 'Test runbook',
        platform_configs: [createOpenAIConfig(process.env.OPENAI_API_KEY || '')],
      };

      try {
        await client.createStream({
          agent: invalidConfig as any,
          handlers: {},
        });
        // If we get here without error, the test should fail
        expect(true).toBe(false);
      } catch (error) {
        // Should get a validation error
        expect(error).toBeDefined();
        expect(error instanceof Error).toBe(true);
      }
    });

    it('should handle connection errors', async () => {
      const invalidClient = createEphemeralAgentClient({
        baseUrl: 'ws://invalid-url-that-does-not-exist:12345',
        timeout: 5000,
      });

      const agentConfig = createBasicAgentConfig({
        name: 'test-agent',
        description: 'Test agent',
        runbook: 'Test runbook',
        platform_configs: [createOpenAIConfig(process.env.OPENAI_API_KEY || '')],
      });

      await expect(
        invalidClient.createStream({
          agent: agentConfig,
          handlers: {},
        }),
      ).rejects.toThrow();
    });
  });

  describe('Test Generic Agent', () => {
    it('should create a generic agent config with default values', () => {
      const platformConfig = createOpenAIConfig(process.env.OPENAI_API_KEY || '');
      const agentConfig = createSaiGenericAgentConfig({
        platform_configs: [platformConfig],
      });

      expect(agentConfig).toBeDefined();
      expect(agentConfig.name).toContain('sai-sdk-generic-agent');
      expect(agentConfig.description).toBe('Sai General Purpose Agent');
      expect(agentConfig.runbook).toContain('OBJECTIVE');
      expect(agentConfig.platform_configs).toHaveLength(1);
    });

    it('should create a generic agent config with custom values', () => {
      const platformConfig = createOpenAIConfig(process.env.OPENAI_API_KEY || '');
      const agentConfig = createSaiGenericAgentConfig({
        platform_configs: [platformConfig],
        name: 'My Custom Agent',
        description: 'A custom agent for testing',
      });

      expect(agentConfig).toBeDefined();
      expect(agentConfig.name).toBe('My Custom Agent');
      expect(agentConfig.description).toBe('A custom agent for testing');
    });

    it('should create a simple generic agent', () => {
      const platformConfig = createOpenAIConfig(process.env.OPENAI_API_KEY || '');
      const agentConfig = createSaiGenericAgentConfig({
        platform_configs: [platformConfig],
        name: 'Simple Agent',
        description: 'Simple description',
      });

      expect(agentConfig).toBeDefined();
      expect(agentConfig.name).toBe('Simple Agent');
      expect(agentConfig.description).toBe('Simple description');
      expect(agentConfig.platform_configs).toHaveLength(1);
    });

    it.skipIf(!hasValidApiKey())(
      'should stream with generic agent successfully',
      async () => {
        const platformConfig = createOpenAIConfig(process.env.OPENAI_API_KEY || '');
        const agentConfig = createSaiGenericAgentConfig({
          platform_configs: [platformConfig],
          name: 'Test Generic Agent',
          description: 'Testing generic agent streaming',
        });

        return new Promise<void>(async (resolve, reject) => {
          const timeoutId = setTimeout(() => {
            reject(new Error('Test timeout after 30 seconds'));
          }, 30000);

          let receivedText = '';

          try {
            const stream = await client.createStream({
              agent: agentConfig,
              messages: [createHumanThreadMessage('Hello! What is your name?')],
              handlers: {
                onMessageEnd: (event) => {
                  console.log('[TEST] Message end:', JSON.stringify(event, null, 2));
                  if (event.data?.content && event.data?.content.length > 0) {
                    const textContent = event.data?.content.find((c) => c.kind === 'text');
                    if (textContent && 'text' in textContent) {
                      receivedText += textContent.text;
                    }
                  }
                },
                onAgentFinished: () => {
                  try {
                    clearTimeout(timeoutId);
                    expect(receivedText.length).toBeGreaterThan(0);
                    expect(receivedText).toContain('Sai');
                    resolve();
                  } catch (e) {
                    reject(e);
                    clearTimeout(timeoutId);
                  }
                },
                onAgentError: (event) => {
                  clearTimeout(timeoutId);
                  reject(new Error(event.error_message));
                },
              },
            });

            if (!stream) {
              clearTimeout(timeoutId);
              reject(new Error('Failed to create stream'));
            }
          } catch (error) {
            clearTimeout(timeoutId);
            reject(error);
          }
        });
      },
      30000,
    ); // 30 second timeout

    it.skipIf(!hasValidApiKey())(
      'should stream with generic agent successfully with sub context',
      async () => {
        const platformConfig = createOpenAIConfig(process.env.OPENAI_API_KEY || '');
        const agentConfig = createSaiGenericAgentConfig({
          platform_configs: [platformConfig],
          agent_context: { raw: '{"name": "John", "age": 30}' },
          name: 'Test Generic Agent',
          description: 'Testing generic agent streaming',
        });

        return new Promise<void>(async (resolve, reject) => {
          const timeoutId = setTimeout(() => {
            reject(new Error('Test timeout after 30 seconds'));
          }, 30000);

          let receivedText = '';

          try {
            const stream = await client.createStream({
              agent: agentConfig,
              messages: [createHumanThreadMessage("Hello! What is John's age?")],
              handlers: {
                onMessageEnd: (event) => {
                  console.log('[TEST] Message end:', JSON.stringify(event, null, 2));
                  if (event.data?.content && event.data?.content.length > 0) {
                    const textContent = event.data?.content.find((c) => c.kind === 'text');
                    if (textContent && 'text' in textContent) {
                      receivedText += textContent.text;
                    }
                  }
                },
                onAgentFinished: () => {
                  try {
                    clearTimeout(timeoutId);
                    expect(receivedText.length).toBeGreaterThan(0);
                    expect(receivedText).toContain('30');
                    resolve();
                  } catch (e) {
                    reject(e);
                    clearTimeout(timeoutId);
                  }
                },
                onAgentError: (event) => {
                  clearTimeout(timeoutId);
                  reject(new Error(event.error_message));
                },
              },
            });

            if (!stream) {
              clearTimeout(timeoutId);
              reject(new Error('Failed to create stream'));
            }
          } catch (error) {
            clearTimeout(timeoutId);
            reject(error);
          }
        });
      },
      30000,
    ); // 30 second timeout for this test
  });
});
