import { createContext, useContext } from 'react';
import { components } from '@sema4ai/workroom-interface';

export type AgentMeta = components['schemas']['AgentMeta'];

export const AgentMetaContext = createContext<AgentMeta | undefined>(undefined);

export const useAgentMetaContext = () => {
  return useContext(AgentMetaContext);
};
