import type { Meta, StoryObj } from '@storybook/react';
import { EphemeralAgentChat } from './components/EphemeralAgentChat';

/**
 * Ephemeral Agent Chat Demo
 *
 * This component demonstrates the Ephemeral Agent feature of the SAI SDK.
 * Ephemeral agents are conversational AI agents that:
 * - Use WebSocket connections for real-time communication
 * - Support multi-turn conversations
 * - Can execute client-side tools
 * - Stream responses as they're generated
 *
 * ## Features
 *
 * - **Real-time Chat**: WebSocket-based streaming for instant responses
 * - **Client Tools**: Define tools that execute in your client (e.g., API calls, UI updates)
 * - **Configurable Agents**: Customize agent name, description, and runbook
 * - **Multi-turn Conversations**: Maintain conversation context across messages
 *
 * ## Use Cases
 *
 * - Customer support chatbots
 * - Interactive assistants
 * - Task automation with user feedback
 * - Dynamic tool execution
 */

const meta = {
  title: 'SAI SDK/Ephemeral Agent Chat',
  component: EphemeralAgentChat,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'Interactive demo of ephemeral agent chat. Create conversational agents with real-time WebSocket communication.',
      },
    },
  },
  tags: ['autodocs'],
  argTypes: {
    apiKey: {
      control: 'text',
      description: 'Your OpenAI API key',
    },
    model: {
      control: 'select',
      options: [
        'gpt-4o',
        'gpt-4o-mini',
        'gpt-4-turbo',
        'gpt-3.5-turbo-1106',
        'gpt-4-1',
        'gpt-4-1-mini',
        'o3-low',
        'o3-high',
        'o4-mini-high',
        'gpt-5-minimal',
        'gpt-5-low',
        'gpt-5-medium',
        'gpt-5-high',
      ],
      description: 'The model to use for the agent',
      defaultValue: 'gpt-4o',
    },
    provider: {
      control: 'select',
      options: ['openai', 'anthropic', 'cortex', 'bedrock'],
      description: 'The provider to use for the agent',
      defaultValue: 'openai',
    },
    agentType: {
      control: 'select',
      options: ['generic', 'agentSetup'],
      description: 'The agent to use for the chat',
      defaultValue: 'void',
    },
  },
} satisfies Meta<typeof EphemeralAgentChat>;

export default meta;
type Story = StoryObj<typeof meta>;
/**
 * Default void assistant chat with proxy (no CORS issues)
 */
export const VoidAssistant: Story = {
  args: {
    baseUrl: 'http://localhost:58885',
    apiKey: 'your-api-key-here',
    model: 'gpt-4o',
    provider: 'openai',
    agentType: 'void',
  },
};

/**
 * Default generic assistant chat with proxy (no CORS issues)
 */
export const GenericAsistant: Story = {
  args: {
    baseUrl: 'http://localhost:58885',
    apiKey: 'your-api-key-here',
    model: 'gpt-4o',
    provider: 'openai',
    agentType: 'generic',
  },
};

/**
 * Default agent setup assistant chat with proxy (no CORS issues)
 */
export const AgentSetupAssistant: Story = {
  args: {
    baseUrl: 'http://localhost:58885',
    apiKey: 'your-api-key-here',
    model: 'gpt-4o',
    provider: 'openai',
    agentType: 'agentSetup',
  },
};
