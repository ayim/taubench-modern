import { resolveWorkroomURL } from './utils';

export type Meta =
  | {
      aceId: string;
      deploymentType: undefined;
      realm: string;
      clientId: string;
      enableRefreshTokens: boolean;
      oidcServerDiscoveryURI: string;
      instanceId: string;
      workroomTokenExchangeUrl: string;
      workroomTenantListUrl: string;
      branding?: {
        logoUrl: string;
        agentAvatarUrl: string;
      };
    }
  | {
      deploymentType: 'spar';
      workroomTenantListUrl: string;
      branding?: {
        logoUrl: string;
        agentAvatarUrl: string;
      };
    };

let __metaPromise: Promise<Meta> | null = null;

export const getMeta = async (): Promise<Meta> => {
  if (__metaPromise) {
    return __metaPromise;
  }

  __metaPromise = (async () => {
    const url = resolveWorkroomURL('/meta');
    const response = await fetch(url, {
      method: 'GET',
    }).then(async (res) => await res.json());

    return response as Meta;
  })();

  return __metaPromise;
};
