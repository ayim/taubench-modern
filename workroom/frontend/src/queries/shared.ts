import { AgentAPIClient } from '~/lib/AgentAPIClient';

export type QueryProps<T = object> = T & {
  agentAPIClient: AgentAPIClient;
};
