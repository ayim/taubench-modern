import { AuthClientOpts } from '@sema4ai/robocloud-ui-utils';
import { Meta } from '~/lib/AgentAPIClient';

export type AuthOptions = { bypassAuth: true } | (AuthClientOpts & { bypassAuth: undefined });
export const getAuthOptions = async (): Promise<AuthOptions> => {
  const url = new URL('/meta', window.location.href).href;
  const meta = (await fetch(url, {
    method: 'GET',
  }).then(async (res) => await res.json())) as Meta;

  if (meta.deploymentType !== undefined) {
    return {
      bypassAuth: true,
    };
  }

  return {
    // we have only one auth type
    type: 'dev_oidc' as AuthClientOpts['type'],
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
