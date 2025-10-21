import { createContext, useContext } from 'react';
import { operations } from '@sema4ai/workroom-interface';
import { Meta } from './meta';

export type TenantMeta = operations['getWorkroomMeta']['responses'][200]['content']['application/json'] &
  Pick<Meta, 'branding'>;

export const TenantContext = createContext<TenantMeta>({
  features: {
    agentEvals: {
      enabled: false,
      reason: '',
    },
    settings: {
      enabled: false,
      reason: '',
    },
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
    deploymentWizard: {
      enabled: false,
      reason: '',
    },
    agentAuthoring: {
      enabled: false,
      reason: '',
    },
    semanticDataModels: {
      enabled: false,
      reason: '',
    },
  },
});

export const useTenantContext = () => {
  return useContext(TenantContext);
};
