import { Configuration } from 'openid-client';
import { beforeEach, describe, expect, it } from 'vitest';
import { OIDCClient, type OIDCPKCEChallenge } from './OIDCClient.js';
import type { MonitoringContext } from '../monitoring/index.js';

describe('OIDCClient', () => {
  const getConfiguration = (): Configuration => {
    const config = new Configuration(
      {
        authorization_endpoint: 'https://auth.example.sema4.ai/oauth/authorize',
        issuer: 'https://auth.example.sema4.ai',
      },
      'test',
    );

    return config;
  };

  const monitoring: MonitoringContext = {
    logger: {
      info: () => {},
      error: () => {},
    },
  };

  it('can be instantiated', () => {
    const client = new OIDCClient({
      oidcClientConfiguration: getConfiguration(),
      monitoring,
    });

    expect(client).toBeInstanceOf(OIDCClient);
  });

  it('can generate PKCE challenges', async () => {
    const challenge = await OIDCClient.generatePKCE();
    expect(challenge).toHaveProperty('codeVerifier');
    expect(challenge).toHaveProperty('codeChallenge');
  });

  describe('instance', () => {
    let client: OIDCClient;

    beforeEach(() => {
      client = new OIDCClient({
        oidcClientConfiguration: getConfiguration(),
        monitoring,
      });
    });

    describe('getAuthorizationUrl', () => {
      const redirectURI = 'https://spar.sema4.ai/tenants/spar/auth/callback';
      let url: string;
      let challenge: OIDCPKCEChallenge;

      beforeEach(async () => {
        challenge = await OIDCClient.generatePKCE();
        url = await client.getAuthorizationUrl({
          codeChallenge: challenge.codeChallenge,
          redirectUri: redirectURI,
          state: 'abc',
        });
      });

      it('sets correct redirect_uri', () => {
        expect(url).toContain(`redirect_uri=${encodeURIComponent(redirectURI)}`);
      });

      it('sets correct PKCE challenge', () => {
        expect(url).toContain('code_challenge_method=S256');
        expect(url).toContain(`code_challenge=${encodeURIComponent(challenge.codeChallenge)}`);
      });

      it('sets state', () => {
        expect(url).toContain('state=');
      });

      it('sets correct response type', () => {
        expect(url).toContain('response_type=code');
      });
    });
  });
});
