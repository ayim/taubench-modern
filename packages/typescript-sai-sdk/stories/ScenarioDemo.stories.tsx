import type { Meta, StoryObj } from '@storybook/react';
import { ScenarioDemo } from './components/ScenarioDemo';
import { AGENT_SETUP_CONTEXT } from './helpers/context';

/**
 * Scenario Demo
 *
 * This component demonstrates the Scenario feature of the SAI SDK.
 * Scenarios are structured AI interactions with:
 * - Custom tools and callbacks
 * - Context configuration (temperature, tokens, etc.)
 * - Streaming execution with tool calls
 *
 * ## Features
 *
 * - **Tool Integration**: Define custom tools with callbacks that get executed during the scenario
 * - **Streaming**: Watch the scenario execution in real-time with incremental updates
 * - **Context Control**: Adjust temperature, max tokens, and system instructions
 *
 * ## Example Use Cases
 *
 * - Weather checking with API integration
 * - Database queries
 * - File operations
 * - Custom business logic
 */
const meta = {
  title: 'SAI SDK/Scenarios',
  component: ScenarioDemo,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'Interactive demo of the Scenario feature. Create AI scenarios with custom tools and stream their execution.',
      },
    },
  },
  tags: ['autodocs'],
  argTypes: {
    apiKey: {
      control: 'text',
      description: 'Your OpenAI API key',
    },
    scenario: {
      control: 'select',
      description: 'The scenario to use for execution',
      options: [
        'generateName',
        'generateDescription',
        'generateRunbook',
        'generateConversationStarter',
        'generateQuestionGroups',
        'generateActionSuggestions',
        'generateRunbookImprovements',
      ],
      defaultValue: 'generateName',
    },
    context: {
      control: 'object',
      description: 'The context to use for scenario execution',
      defaultValue: AGENT_SETUP_CONTEXT,
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
      description: 'The model to use for scenario execution',
      defaultValue: 'gpt-4o',
    },
    provider: {
      control: 'select',
      options: ['openai', 'anthropic', 'cortex', 'bedrock'],
      description: 'The provider to use for scenario execution',
      defaultValue: 'openai',
    },
  },
} satisfies Meta<typeof ScenarioDemo>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default generate name scenario
 */
export const GenerateNameScenario: Story = {
  args: {
    apiKey: 'your-api-key-here',
    scenario: 'generateName',
    context: AGENT_SETUP_CONTEXT,
    model: 'gpt-4o',
    provider: 'openai',
  },
};

/**
 * Default generate description scenario
 */
export const GenerateDescriptionScenario: Story = {
  args: {
    apiKey: 'your-api-key-here',
    scenario: 'generateDescription',
    context: AGENT_SETUP_CONTEXT,
    model: 'gpt-4o',
    provider: 'openai',
  },
};

/**
 * Default generate runbook scenario
 */
export const GenerateRunbookScenario: Story = {
  args: {
    apiKey: 'your-api-key-here',
    scenario: 'generateRunbook',
    context: AGENT_SETUP_CONTEXT,
    model: 'gpt-4o',
    provider: 'openai',
  },
};

/**
 * Default generate conversation starter scenario
 */
export const GenerateConversationStarterScenario: Story = {
  args: {
    apiKey: 'your-api-key-here',
    scenario: 'generateConversationStarter',
    context: AGENT_SETUP_CONTEXT,
    model: 'gpt-4o',
    provider: 'openai',
  },
};

/**
 * Default generate question groups scenario
 */
export const GenerateQuestionGroupsScenario: Story = {
  args: {
    apiKey: 'your-api-key-here',
    scenario: 'generateQuestionGroups',
    context: AGENT_SETUP_CONTEXT,
    model: 'gpt-4o',
    provider: 'openai',
  },
};

/**
 * Default generate action suggestions scenario
 */
export const GenerateActionSuggestionsScenario: Story = {
  args: {
    apiKey: 'your-api-key-here',
    scenario: 'generateActionSuggestions',
    context: AGENT_SETUP_CONTEXT,
    model: 'gpt-4o',
    provider: 'openai',
  },
};

/**
 * Default generate runbook improvements scenario
 */
export const GenerateRunbookImprovementsScenario: Story = {
  args: {
    apiKey: 'your-api-key-here',
    scenario: 'generateRunbookImprovements',
    context: AGENT_SETUP_CONTEXT,
    model: 'gpt-4o',
    provider: 'openai',
  },
};
