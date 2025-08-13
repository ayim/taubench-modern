/**
 * Tests for ephemeral agent streaming functionality
 */
import { describe, it, expect, beforeEach } from 'vitest';

import {
  EphemeralAgentClient,
  createEphemeralAgentClient,
  createBasicAgentConfig,
  createHumanMessage,
  createSystemMessage,
  EphemeralEvent,
} from '../src/agent-ephemeral/index';

// TODO: Remove this skip when Ephemeral Agents are ready for testing
describe.skip('EphemeralAgentClient', () => {
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

  describe('createStream', () => {
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

    it.skipIf(!hasValidApiKey())(
      'should create a stream successfully',
      async () => {
        const agentConfig = createBasicAgentConfig({
          name: 'test-agent',
          description: 'Test agent for integration testing',
          runbook: 'You are a helpful assistant. Respond with "Hello from ephemeral agent!"',
          openai_api_key: process.env.OPENAI_API_KEY || '',
        });

        return new Promise<void>(async (resolve, reject) => {
          const timeoutId = setTimeout(() => {
            reject(new Error('Test timeout after 30 seconds'));
          }, 30000);

          const stream = await client.createStream({
            agent: agentConfig,
            messages: [createHumanMessage('Hello. What can you do?')],
            handlers: {
              onAgentReady: (event) => {
                console.log('Agent ready:', event.agent_id);
                expect(event.run_id).toBeDefined();
                expect(event.thread_id).toBeDefined();
                expect(event.agent_id).toBeDefined();
                expect(event.timestamp).toBeDefined();
              },
              onMessage: (event) => {
                console.log('Message received:', event.content);
                expect(event.content).toBeDefined();
              },
              onAgentFinished: (event) => {
                console.log('Agent finished');
                clearTimeout(timeoutId);
                resolve();
              },
              onAgentError: (event) => {
                console.error('Agent error:', event.error_message);
                clearTimeout(timeoutId);
                reject(new Error(`Agent error: ${event.error_message}`));
              },
              onClose: (code, reason) => {
                console.log('Connection closed:', code, reason);
                resolve();
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

    it('should handle validation errors', async () => {
      // Test with completely invalid agent configuration that should fail validation
      const invalidConfig = {
        name: '', // Empty name should fail validation
        description: 'Test agent',
        runbook: 'Test runbook',
        openai_api_key: process.env.OPENAI_API_KEY || '',
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
        openai_api_key: process.env.OPENAI_API_KEY || '',
      });

      await expect(
        invalidClient.createStream({
          agent: agentConfig,
          handlers: {},
        }),
      ).rejects.toThrow();
    });

    it.skipIf(!hasValidApiKey()).only(
      'should keep stream open for 10 seconds and send messages every 3 seconds',
      async () => {
        const agentConfig = createBasicAgentConfig({
          name: 'test-streaming-agent',
          description: 'Test agent for continuous streaming',
          runbook: `You are a helpful assistant designed for continuous conversation testing. 
          
IMPORTANT: You will receive multiple messages over the next 10 seconds. Do NOT finish or close the conversation after the first message. 

Your role:
- Respond briefly to each message you receive
- Stay active and ready to receive more messages
- Keep the conversation going until the user explicitly says goodbye
- Do not assume the conversation is over after any single message

Wait for and respond to each message as it comes in.`,
          openai_api_key: process.env.OPENAI_API_KEY || '',
        });

        return new Promise<void>(async (resolve, reject) => {
          let messageCount = 0;
          let intervalId: NodeJS.Timeout;
          let timeoutId: NodeJS.Timeout;
          let streamRef: any = null;
          let tenSecondsCompleted = false;
          const startTime = Date.now();

          const cleanup = () => {
            if (intervalId) clearInterval(intervalId);
            if (timeoutId) clearTimeout(timeoutId);
          };

          try {
            const stream = await client.createStream({
              agent: agentConfig,
              messages: [
                createHumanMessage(
                  'Hello! This is a 10-second streaming test. I will send you multiple messages every 3 seconds. Please acknowledge and stay ready for more messages. Do NOT close the conversation yet.',
                ),
              ],
              handlers: {
                onAgentReady: (event) => {
                  console.log('🚀 Agent ready:', event.agent_id);
                  console.log('   Run ID:', event.run_id);
                  console.log('   Thread ID:', event.thread_id);
                  console.log('   Starting 10-second streaming test...\n');

                  // Start sending messages every 3 seconds
                  intervalId = setInterval(() => {
                    messageCount++;
                    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
                    const message = `Message #${messageCount} at ${elapsed}s - Current time: ${new Date().toLocaleTimeString()}`;
                    console.log('📤 Sending message:', message);

                    // Send message to the stream using the correct API
                    if (streamRef && streamRef.sendMessage) {
                      try {
                        streamRef.sendMessage(createHumanMessage(message));
                      } catch (error) {
                        console.error('❌ Error sending message:', error);
                      }
                    }
                  }, 3000);

                  // Stop after 10 seconds
                  timeoutId = setTimeout(() => {
                    tenSecondsCompleted = true;
                    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
                    console.log(`\n⏰ 10 seconds elapsed (actual: ${elapsed}s), sending final message...`);

                    // Send a final goodbye message to properly close the conversation
                    if (streamRef && streamRef.sendMessage) {
                      try {
                        streamRef.sendMessage(
                          createHumanMessage('Thank you! This concludes the 10-second test. Goodbye!'),
                        );
                        console.log('📤 Final message sent: Thank you! This concludes the 10-second test. Goodbye!');
                      } catch (error) {
                        console.error('❌ Error sending final message:', error);
                      }
                    }

                    // Wait a bit for the final response, then clean up
                    setTimeout(() => {
                      console.log('🔧 Cleaning up and closing stream...');
                      cleanup();

                      // Close the stream
                      if (streamRef && streamRef.close) {
                        streamRef.close();
                      }

                      setTimeout(() => resolve(), 1000); // Give some time for cleanup
                    }, 2000); // Wait 2 seconds for final response
                  }, 10000);
                },
                onMessage: (event) => {
                  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
                  console.log(`📥 Agent response at ${elapsed}s:`, event.content);
                },
                onAgentFinished: (event) => {
                  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
                  console.log(`✅ Agent finished processing at ${elapsed}s`);

                  if (!tenSecondsCompleted) {
                    // Agent finished before 10 seconds - this is expected behavior for ephemeral agents
                    // but we want to track it for our test
                    console.log(`⚠️ Agent finished early at ${elapsed}s (before 10s target)`);
                    // Don't fail the test here - the connection close handler will handle it
                  }
                },
                onAgentError: (event) => {
                  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
                  console.error(`❌ Agent error at ${elapsed}s:`, event.error_message);
                  cleanup();
                  reject(new Error(`Agent error: ${event.error_message}`));
                },
                onClose: (code, reason) => {
                  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
                  console.log(`🔌 Connection closed at ${elapsed}s:`, code, reason);
                  cleanup();

                  if (!tenSecondsCompleted) {
                    // Connection closed before 10 seconds - this should fail the test
                    reject(
                      new Error(
                        `Connection closed prematurely after ${elapsed}s (expected 10s). Code: ${code}, Reason: ${reason}`,
                      ),
                    );
                  } else {
                    // Connection closed after 10 seconds as expected
                    console.log('✅ Test completed successfully - connection remained open for full 10 seconds');
                    resolve();
                  }
                },
              },
            });

            streamRef = stream;

            if (!stream) {
              cleanup();
              reject(new Error('Failed to create stream'));
            }
          } catch (error) {
            cleanup();
            reject(error);
          }
        });
      },
      20000, // 20 second timeout for this test (10s + 2s for final response + buffer)
    );
  });
});
