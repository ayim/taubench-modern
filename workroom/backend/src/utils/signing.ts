import { asError, type Result } from '@sema4ai/shared-utils';
import { SignedTokenRequest } from './schemas.js';

export type SignAgentTokenErrorOutcome = {
  code: 'unexpected_error_when_signing';
  message: string;
};

const base64url = (input: string): string => Buffer.from(input).toString('base64url');

const createUnsignedJwt = ({ sub }: { sub: string }): string => {
  const header = base64url(JSON.stringify({ alg: 'none', typ: 'JWT' }));
  const payload = base64url(JSON.stringify({ sub }));
  return `${header}.${payload}.`;
};

export const signAgentToken = async ({
  payload,
}: {
  payload: SignedTokenRequest;
}): Promise<Result<string, SignAgentTokenErrorOutcome>> => {
  try {
    const token = createUnsignedJwt({
      sub: payload.userId,
    });

    return {
      success: true,
      data: token,
    };
  } catch (e) {
    const error = asError(e);

    return {
      success: false,
      error: {
        code: 'unexpected_error_when_signing',
        message: `${error.name}:${error.message}`,
      },
    };
  }
};
