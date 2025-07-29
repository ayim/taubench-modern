import { OAuthClient, OAuthProvider, OAuthProviderSettings } from '@sema4ai/oauth-client';
import { Agent } from '~/types';

// TODO: v2 integration, ask to add mode in types
export const isConversationalAgent = (agent: Agent) => agent && agent.metadata?.mode !== 'worker';
export const isWorkerAgent = (agent: Agent) => agent && agent.metadata?.mode === 'worker';

export const isProviderConfigured = (
  providerName: OAuthProvider,
  providedSettings: Partial<OAuthProviderSettings>,
): boolean => {
  const defaultValues = OAuthClient.getProviderDefaults(providerName);
  const settings = { ...defaultValues, ...providedSettings };

  return !!settings.clientId && !!settings.redirectUri;
};

export const getPreferenceKey = (agent: Agent) => `preffered-thread-or-work-item-${agent.id}`;

export const setUserPreferenceId = (key: string, id: string) => {
  localStorage.setItem(key, id);
};

export const getUserPreferenceId = (key: string) => {
  return localStorage.getItem(key);
};

export const removeUserPreferenceId = (key: string) => {
  localStorage.removeItem(key);
};
