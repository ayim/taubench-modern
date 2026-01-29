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
      auth?: 'session';
      deploymentType: 'spar';
      version: string;
      workroomTenantListUrl: string;
      branding?: {
        logoUrl: string;
        agentAvatarUrl: string;
      };
    };

let metaPromise: Promise<Meta> | null = null;

export const getMeta = async (): Promise<Meta> => {
  if (metaPromise) {
    return metaPromise;
  }

  metaPromise = (async () => {
    const url = resolveWorkroomURL('/meta');
    const response = await fetch(url, {
      method: 'GET',
    }).then(async (res) => res.json());

    return response as Meta;
  })();

  return metaPromise;
};
