import type { Meta, StoryObj } from '@storybook/react';
import { AgentPromptDemo } from './components/AgentPrompt';

/**
 * Agent Prompt Demo
 *
 * This component demonstrates the Agent Prompt feature of the SAI SDK.
 * It allows you to:
 * - Send prompts to an AI agent
 * - Configure system instructions
 * - Stream responses in real-time
 * - View detailed response metadata
 *
 * ## Configuration
 *
 * To use this demo, you need to provide:
 * - **Base URL**: Leave empty (default) to use the proxy, or provide a full URL (e.g., `http://localhost:58885`)
 * - **API Key**: Your OpenAI API key
 * - **Model**: The model to use (default: `gpt-4o`)
 *
 * **Note**: Using an empty Base URL avoids CORS issues by routing requests through the Storybook dev server proxy.
 */
const meta = {
  title: 'SAI SDK/Agent Prompt',
  component: AgentPromptDemo,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'Interactive demo of the Agent Prompt feature. Send prompts and receive AI-generated responses.',
      },
    },
  },
  tags: ['autodocs'],
  argTypes: {
    apiKey: {
      control: 'text',
      description: 'Your OpenAI API key',
    },
    provider: {
      control: 'select',
      options: ['openai', 'anthropic', 'google', 'azure'],
      description: 'The provider to use for generation',
      defaultValue: 'openai',
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
      description: 'The model to use for generation',
      defaultValue: 'gpt-4o',
    },
  },
} satisfies Meta<typeof AgentPromptDemo>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default story with basic configuration
 */
export const Default: Story = {
  args: {
    apiKey: 'your-api-key-here',
    model: 'gpt-4o',
    provider: 'openai',
  },
};
