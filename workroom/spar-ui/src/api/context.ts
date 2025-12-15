import { createContext, useContext } from 'react';

import type { SparAPIClient } from './index';

export type SparUIPlatformConfig = {
  snowflakeEAIUrl: string | null;
};

export const SparUIContext = createContext<{
  platformConfig: SparUIPlatformConfig;
  sparAPIClient: SparAPIClient;
}>({
  platformConfig: {
    snowflakeEAIUrl: null,
  },
  sparAPIClient: undefined!,
});

export const useSparUIContext = () => {
  return useContext(SparUIContext);
};
