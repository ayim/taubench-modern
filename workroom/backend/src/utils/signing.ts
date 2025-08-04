import { getTokenSigner } from '@sema4ai/robocloud-auth-utils';
import type { Configuration } from '../configuration.js';
import type { Result } from './result.js';
import { SignedTokenRequest } from './schemas.js';

export type SignAgentTokenErrorOutcome =
  | {
      code: 'invalid_signing_result';
      message: string;
    }
  | {
      code: 'signing_failed';
      message: string;
    };

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
}): Promise<Result<string, SignAgentTokenErrorOutcome>> => {
  if (configuration.auth.type === 'none') {
    throw new Error(`Unsupported auth type for token generation: ${configuration.auth.type}`);
  }
  const tokenB64 = configuration.auth.jwtPrivateKeyB64;

  const getPrivateKey = async (): Promise<PrivateKeyResult> => ({
    keyId: AGENT_TOKEN_KEY_ID,
    privateKey: Buffer.from(tokenB64, 'base64').toString('utf-8'),
  });

  try {
    const signer = getTokenSigner({
      tokenInterface: SignedTokenRequest,
      getPrivateKey,
    });

    const signerResult = await signer.sign({
      audience: AGENT_TOKEN_AUDIENCE,
      expiresInSeconds: AGENT_TOKEN_EXPIRY,
      issuer: AGENT_TOKEN_ISSUER,
      subject: payload.userId,
      token: payload,
    });

    if (signerResult.isValid) {
      return {
        success: true,
        data: signerResult.token,
      };
    } else {
      return {
        success: false,
        error: {
          code: 'invalid_signing_result',
          message: signerResult.reason.message,
        },
      };
    }
  } catch (err) {
    const error = err as Error;

    return {
      success: false,
      error: {
        code: 'signing_failed',
        message: `Failed signing agent token: ${error.message}`,
      },
    };
  }
};
