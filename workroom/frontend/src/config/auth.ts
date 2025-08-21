import { AuthClientOpts } from '@sema4ai/robocloud-ui-utils';
import { getMeta } from '~/lib/meta';

export type AuthOptions = { bypassAuth: true } | (AuthClientOpts & { bypassAuth: undefined });
export const getAuthOptions = async (): Promise<AuthOptions> => {
  const meta = await getMeta();

  if (meta.deploymentType) {
    return {
      bypassAuth: true,
    };
  }

  return {
    // we have only one auth type
    type: 'dev_oidc' as AuthClientOpts['type'],
    // Redirect to the ACE control-plane endpoint, which will subsequently redirect
    // back to workroom
    redirectUri: `${window.location.origin}/signin-callback`,
    baseUrls: [window.location.origin],
    oidc: {
      clientId: meta.clientId,
      enableRefreshTokens: meta.enableRefreshTokens,
      realm: meta.realm,
      instanceId: meta.instanceId,
      oidcServerDiscoveryURI: meta.oidcServerDiscoveryURI,
    },
    // not used for Workroom!
    // filled with fake values just to silence typing errors
    auth0: {
      clientId: '-no-client-id',
      domain: '-no-domain',
      idSiteUrl: '-no-site-url',
      userFrontPage: '-no-user-front-page',
    },
    bypassAuth: undefined,
  };
};
