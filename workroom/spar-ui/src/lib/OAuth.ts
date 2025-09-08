import { OAuthProvider } from '@sema4ai/oauth-client';

export type AgentOAuthProviderState = {
  isAuthorized: boolean;
  providerType: OAuthProvider;
  uri: string;
  scopes: string[];
};
