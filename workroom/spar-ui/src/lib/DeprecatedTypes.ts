import { OAuthProvider } from '@sema4ai/oauth-client';

/**
 * @deprecated Do not use
 * Action Package information used for SparAPIClient.getActionDetails for OAuth2 information
 */
enum ActionSecretType {
  'Secret' = 'Secret',
  'Variable' = 'Variable',
  'OAuth2Secret' = 'OAuth2Secret',
}

/**
 * @deprecated Do not use
 * Action Package information used for SparAPIClient.getActionDetails for OAuth2 information
 */
type ActionPackageSecretText = {
  actionName: string;
  type: ActionSecretType.Secret | ActionSecretType.Variable;
  name: string;
  description: string;
  required?: boolean;
};

/**
 * @deprecated Do not use
 * Action Package information used for SparAPIClient.getActionDetails for OAuth2 information
 */
type ActionPackageSecretOAuth = {
  actionName: string;
  type: ActionSecretType.OAuth2Secret;
  name: string;
  scopes: string[];
  provider: OAuthProvider;
  description?: string;
  required?: boolean;
};

/**
 * @deprecated Do not use
 * Action Package information used for SparAPIClient.getActionDetails for OAuth2 information
 */
type ActionPackageMetadata = {
  name: string;
  description: string;
  iconPath?: string;
  actions: {
    name: string;
    friendlyName: string;
    description: string;
  }[];
  settings: (ActionPackageSecretText | ActionPackageSecretOAuth)[];
  dataSources?: unknown;
};

/**
 * @deprecated Do not use
 * Action Package information used for SparAPIClient.getActionDetails for OAuth2 information
 */
export type ActionPackage = {
  name: string;
  slugName: string;
  path: string;
  datadirPath: string;
  isBundled: boolean;
  metadata: ActionPackageMetadata;
  actionServerPort?: number;
};

/**
 * @deprecated Do not use
 * Action Package information used for SparAPIClient.getActionDetails for OAuth2 information
 */
export const isOAuthSecret = (
  setting: ActionPackageMetadata['settings'][number],
): setting is ActionPackageSecretOAuth => setting.type === ActionSecretType.OAuth2Secret;
