/**
 * overrides type for back compatibilty with v1
 */
import { components } from './schema.gen';
import type { components as v1 } from './v1/schema.d.ts';

export type Thread = components['schemas']['Thread'] & {
  thread_id: string;
  created_at: string;
  updated_at: string;
  agent_id: string;
  metadata?: Record<string, never> & { langsmith_urls?: string[] };
  messages: ThreadMessage[];
};

export type ThreadTextContent = components['schemas']['ThreadTextContent'] & {
  kind: 'text';
};

export type ThreadFormattedTextContent =
  components['schemas']['ThreadFormattedTextContent'] & {
    kind: 'formatted-text';
  };

export type ThreadQuickActionsContent =
  components['schemas']['ThreadQuickActionsContent'] & {
    kind: 'quick_actions';
  };

export type ThreadVegaChartContent =
  components['schemas']['ThreadVegaChartContent'] & {
    kind: 'vega_chart';
  };

export type ThreadToolUsageContent =
  components['schemas']['ThreadToolUsageContent'] & {
    kind: 'tool_call';
  };

export type ThreadThoughtContent =
  components['schemas']['ThreadThoughtContent'] & {
    kind: 'thought';
  };

export type ThreadAttachmentContent =
  components['schemas']['ThreadAttachmentContent'] & {
    kind: 'attachment';
  };

export type ThreadContent =
  | ThreadTextContent
  | ThreadFormattedTextContent
  | ThreadQuickActionsContent
  | ThreadVegaChartContent
  | ThreadToolUsageContent
  | ThreadThoughtContent
  | ThreadAttachmentContent;

type Overwrite<T, U> = Pick<T, Exclude<keyof T, keyof U>> & U;

export type ThreadMessage = Overwrite<
  components['schemas']['ThreadMessage'],
  {
    created_at: string;
    updated_at: string;
    message_id: string;

    content: ThreadContent[];
  }
>;

export type ThreadAgentMessage = ThreadMessage & {
  role: 'agent';
};

export type ThreadUserMessage = ThreadMessage & {
  role: 'user';
};

export type ActionPackage = components['schemas']['ActionPackageCompat'] & {
  url: string;
  api_key: string;
};

export type Agent = components['schemas']['AgentCompat'] & {
  created_at: string;
  updated_at: string;
  agent_id: string;
  id: string;
  model:
    | v1['schemas']['OpenAIGPT']
    | v1['schemas']['AzureGPT']
    | v1['schemas']['AnthropicClaude']
    | v1['schemas']['AmazonBedrock']
    | v1['schemas']['Ollama']
    | v1['schemas']['SnowflakeCortex'];
  advanced_config: v1['schemas']['AgentAdvancedConfig'];
  action_packages: ActionPackage[];
  metadata: v1['schemas']['AgentMetadata'];
};

export type ContextStats = {
  context_window_size: number;
  tokens_per_message: Record<string, number>;
};

export type QuestionGroup = components['schemas']['QuestionGroup'] & {
  questions: string[];
};
