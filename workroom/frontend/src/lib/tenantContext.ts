import { createContext, useContext } from 'react';
import { operations } from '@sema4ai/workroom-interface';
import { Meta } from './meta';

export const TenantContext = createContext<
  operations['getWorkroomMeta']['responses'][200]['content']['application/json'] & Pick<Meta, 'branding'>
>({
  features: {
    documentIntelligence: {
      enabled: false,
      reason: '',
    },
    developerMode: {
      enabled: false,
      reason: '',
    },
    mcpServersManagement: {
      enabled: false,
      reason: '',
    },
    agentDetails: {
      enabled: false,
      reason: '',
    },
  },
});

export const useTenantContext = () => {
  return useContext(TenantContext);
};
