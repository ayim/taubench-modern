import { createContext, useContext } from 'react';

import type { SparAPIClient } from './index';

export const SparUIContext = createContext<{
  sparAPIClient: SparAPIClient;
}>({
  sparAPIClient: undefined!,
});

export const useSparUIContext = () => {
  return useContext(SparUIContext);
};
