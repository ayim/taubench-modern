import { OAuthProvider } from '@sema4ai/oauth-client';

export type AgentOAuthProviderState = {
  id: string;
  isAuthorized: boolean;
  providerType: OAuthProvider;
  uri: string;
  scopes: string[];
};
