import { useAgentMetaContext } from '~/lib/agentMetaContext';
import { useTenantContext } from '~/lib/tenantContext';

export enum FeatureFlag {
  showActionLogs = 'showActionLogs',
  canCreateAgents = 'canCreateAgents',
  canConfigureAgents = 'canConfigureAgents',
  deploymentWizard = 'deploymentWizard',
  agentDetails = 'agentDetails',
  documentIntelligence = 'documentIntelligence',
  semanticDataModels = 'semanticDataModels',
  agentFeedback = 'agentFeedback',
  agentChatInput = 'agentChatInput',
  violetAgentChat = 'violetAgentChat',
}

export const useFeatureFlag = (feature: FeatureFlag): { enabled: true } | { enabled: false; message?: string } => {
  const agentMeta = useAgentMetaContext();
  const tenantMeta = useTenantContext();

  const featureFlagFallback = { enabled: false };

  switch (feature) {
    case FeatureFlag.showActionLogs:
      return { enabled: tenantMeta.features.developerMode.enabled };
    case FeatureFlag.deploymentWizard:
      return { enabled: tenantMeta.features.deploymentWizard.enabled };
    case FeatureFlag.canCreateAgents:
      return { enabled: tenantMeta.features.agentAuthoring.enabled };
    case FeatureFlag.canConfigureAgents:
      return { enabled: tenantMeta.features.agentConfiguration.enabled };
    case FeatureFlag.agentDetails:
      return { enabled: tenantMeta.features.agentDetails.enabled };
    case FeatureFlag.documentIntelligence:
      return { enabled: tenantMeta.features.documentIntelligence.enabled };
    case FeatureFlag.semanticDataModels:
      return { enabled: tenantMeta.features.semanticDataModels.enabled };
    case FeatureFlag.agentFeedback:
      return agentMeta?.workroomUi?.feedback ?? featureFlagFallback;
    case FeatureFlag.agentChatInput:
      return agentMeta?.workroomUi?.chatInput ?? featureFlagFallback;
    case FeatureFlag.violetAgentChat:
      return { enabled: tenantMeta.features.developerMode.enabled };
    default:
      feature satisfies never;
      return featureFlagFallback;
  }
};
