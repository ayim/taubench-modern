import { createContext, useContext } from 'react';

import type { AgentAPIClient } from '~/lib/AgentAPIClient';

export type SparUIPlatformConfig = {
  snowflakeEAIUrl: string | null;
};

export const SparUIContext = createContext<{
  platformConfig: SparUIPlatformConfig;
  agentAPIClient: AgentAPIClient;
  tenantId: string;
}>({
  platformConfig: {
    snowflakeEAIUrl: null,
  },
  agentAPIClient: undefined!,
  tenantId: undefined!,
});

export const useSparUIContext = () => {
  return useContext(SparUIContext);
};
