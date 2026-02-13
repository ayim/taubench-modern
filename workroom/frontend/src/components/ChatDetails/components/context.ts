/* eslint-disable @typescript-eslint/no-unused-vars */
import { createContext, FC, useContext } from 'react';
import { components } from '@sema4ai/agent-server-interface';

import { useAgentQuery } from '~/queries/agents';

type Agent = NonNullable<ReturnType<typeof useAgentQuery>['data']>;
export type AgentDetailsComponent = FC<{ agent: Agent }>;

export const AgentDetailsContext = createContext<{
  agent: Agent;
  updateAgent: (payload: Partial<components['schemas']['UpsertAgentPayload']>) => Promise<void>;
}>({
  agent: null!,
  updateAgent: () => Promise.resolve(),
});

export const useAgentDetailsContext = () => {
  return useContext(AgentDetailsContext);
};
