import { describe, expect, it } from 'vitest';
import { sessionsEqual } from './payload.js';

describe('sessionsEqual', () => {
  it('returns true for matching sessions', () => {
    expect(
      sessionsEqual(
        { auth: { stage: 'auth-callback', codeVerifier: 'abc' }, authType: 'oidc' },
        { auth: { stage: 'auth-callback', codeVerifier: 'abc' }, authType: 'oidc' },
      ),
    ).toEqual(true);
  });

  it('returns false for non-matching sessions', () => {
    expect(
      sessionsEqual(
        { auth: { stage: 'auth-callback', codeVerifier: 'abc' }, authType: 'oidc' },
        {
          auth: {
            stage: 'authenticated',
            tokens: {
              accessToken: 'abc',
              expiresAt: 0,
              idToken: 'def',
              refreshToken: 'ghi',
              state: '...',
              tokenType: 'bearer',
              userId: 'test@sema4.ai',
            },
          },
          authType: 'oidc',
        },
      ),
    ).toEqual(false);
  });
});
