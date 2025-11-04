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
    workerAgents: {
      enabled: false,
      reason: '',
    },
  },
});

export const useTenantContext = () => {
  return useContext(TenantContext);
};

export const shouldDisplayConfigurationSidebarLink = (tenantMeta: TenantMeta) => {
  // This must be kept in sync with the flags used for showing / hidding tabs here:
  // https://github.com/Sema4AI/agent-platform/blob/670ae292abb300d205b8f437b6caa4cba63ac5b0/workroom/frontend/src/routes/tenants/%24tenantId/configuration.tsx#L15
  return tenantMeta.features.deploymentWizard.enabled || tenantMeta.features.settings.enabled;
};
