import { useTenantContext } from '~/lib/tenantContext';

export enum FeatureFlag {
  agentChatInput = 'agentChatInput',
  agentDetails = 'agentDetails',
  agentFeedback = 'agentFeedback',
  canConfigureAgents = 'canConfigureAgents',
  canCreateAgents = 'canCreateAgents',
  deploymentWizard = 'deploymentWizard',
  documentIntelligence = 'documentIntelligence',
  semanticDataModels = 'semanticDataModels',
  showActionLogs = 'showActionLogs',
  violetAgentChat = 'violetAgentChat',
}

export const useFeatureFlag = (feature: FeatureFlag): { enabled: true } | { enabled: false; message?: string } => {
  const tenantMeta = useTenantContext();

  switch (feature) {
    case FeatureFlag.agentChatInput:
      return { enabled: true };
    case FeatureFlag.agentDetails:
      return { enabled: tenantMeta.features.agentDetails.enabled };
    case FeatureFlag.agentFeedback:
      return { enabled: false };
    case FeatureFlag.canConfigureAgents:
      return { enabled: tenantMeta.features.agentConfiguration.enabled };
    case FeatureFlag.canCreateAgents:
      return { enabled: tenantMeta.features.agentAuthoring.enabled };
    case FeatureFlag.deploymentWizard:
      return { enabled: tenantMeta.features.deploymentWizard.enabled };
    case FeatureFlag.documentIntelligence:
      return { enabled: tenantMeta.features.documentIntelligence.enabled };
    case FeatureFlag.semanticDataModels:
      return { enabled: tenantMeta.features.semanticDataModels.enabled };
    case FeatureFlag.showActionLogs:
      return { enabled: tenantMeta.features.developerMode.enabled };
    case FeatureFlag.violetAgentChat:
      return { enabled: tenantMeta.features.developerMode.enabled };
    default:
      feature satisfies never;
      return { enabled: false };
  }
};
