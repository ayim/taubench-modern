import { createContext, useContext } from 'react';
import type { Meta } from './meta';
import type { TrpcOutput } from './trpc';

export type TenantMeta = TrpcOutput['configuration']['getTenantConfig'] & Pick<Meta, 'branding'>;

const disabledFeature = { enabled: false, reason: null } as const;

export const TenantContext = createContext<TenantMeta>({
  features: {
    agentAuthoring: disabledFeature,
    agentConfiguration: disabledFeature,
    agentDetails: disabledFeature,
    agentEvals: disabledFeature,
    deploymentWizard: disabledFeature,
    developerMode: disabledFeature,
    documentIntelligence: disabledFeature,
    mcpServersManagement: disabledFeature,
    publicAPI: disabledFeature,
    semanticDataModels: disabledFeature,
    settings: disabledFeature,
    userManagement: disabledFeature,
    workerAgents: disabledFeature,
  },
});

export const useTenantContext = () => {
  return useContext(TenantContext);
};

export const shouldDisplayConfigurationSidebarLink = (tenantMeta: TenantMeta) => {
  // This must be kept in sync with the flags used for showing / hidding tabs here:
  // https://github.com/Sema4AI/agent-platform/blob/670ae292abb300d205b8f437b6caa4cba63ac5b0/workroom/frontend/src/routes/tenants/%24tenantId/configuration.tsx#L15
  return (
    tenantMeta.features.deploymentWizard.enabled ||
    tenantMeta.features.publicAPI.enabled ||
    tenantMeta.features.settings.enabled
  );
};
