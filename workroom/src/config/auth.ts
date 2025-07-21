import { AuthClientOpts } from '@sema4ai/robocloud-ui-utils';
import { Meta } from '~/lib/AgentAPIClient';

export type AuthOptions = { bypassAuth: true } | (AuthClientOpts & { bypassAuth: undefined });
export const getAuthOptions = async (): Promise<AuthOptions> => {
  if (import.meta.env.MODE === 'development') {
    console.warn('This should not be invoked in prod!', { deploymentType: import.meta.env.VITE_DEPLOYMENT_TYPE });
    return Promise.resolve({
      type: import.meta.env.VITE_AUTHORIZATION_PROVIDER_TYPE as AuthClientOpts['type'],
      redirectUri: `${window.location.origin}/signin-callback`,
      baseUrls: [import.meta.env.VITE_INSTANCE_BASE_URL],
      oidc: {
        clientId: import.meta.env.VITE_DEV_OIDC_CLIENT_ID,
        enableRefreshTokens: import.meta.env.VITE_DEV_OIDC_ALLOW_REFRESH_TOKENS_WITH_ROTATION,
        realm: import.meta.env.VITE_DEV_OIDC_REALM,
        instanceId: import.meta.env.VITE_DEV_CONTROL_ROOM_INSTANCE_ID,
        oidcServerDiscoveryURI: import.meta.env.VITE_DEV_OIDC_DISCOVERY_URI,
      },
      // not used for Workroom!
      // filled with fake values just to silence typing errors
      auth0: {
        clientId: '-no-client-id',
        domain: '-no-domain',
        idSiteUrl: '-no-site-url',
        userFrontPage: '-no-user-front-page',
      },
      bypassAuth:
        import.meta.env.VITE_DEPLOYMENT_TYPE === 'spcs' || import.meta.env.VITE_DEPLOYMENT_TYPE === 'spar'
          ? true
          : undefined,
    });
  }

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
