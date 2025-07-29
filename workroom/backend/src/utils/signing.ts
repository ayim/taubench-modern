import { getTokenSigner } from '@sema4ai/robocloud-auth-utils';
import type { Configuration } from '../configuration.js';
import { SignedTokenRequest } from './schemas.js';

export type SigningResult = Awaited<ReturnType<ReturnType<typeof getTokenSigner>['sign']>>;

interface PrivateKeyResult {
  privateKey: string;
  keyId: string;
}

const AGENT_TOKEN_AUDIENCE = 'agent_server';
const AGENT_TOKEN_EXPIRY = 300; // 5 min
const AGENT_TOKEN_ISSUER = 'spar';
const AGENT_TOKEN_KEY_ID = 'agent_server_v2';

export const signAgentToken = async ({
  configuration,
  payload,
}: {
  configuration: Configuration;
  payload: SignedTokenRequest;
}) => {
  if (configuration.auth.type !== 'google') {
    throw new Error(`Unsupported auth type for token generation: ${configuration.auth.type}`);
  }
  const tokenB64 = configuration.auth.jwtPrivateKeyB64;

  const getPrivateKey = async (): Promise<PrivateKeyResult> => ({
    keyId: AGENT_TOKEN_KEY_ID,
    privateKey: Buffer.from(tokenB64, 'base64').toString('utf-8'),
  });
  const signer = getTokenSigner({
    tokenInterface: SignedTokenRequest,
    getPrivateKey,
  });

  return await signer.sign({
    audience: AGENT_TOKEN_AUDIENCE,
    expiresInSeconds: AGENT_TOKEN_EXPIRY,
    issuer: AGENT_TOKEN_ISSUER,
    subject: payload.userId,
    token: payload,
  });
};
