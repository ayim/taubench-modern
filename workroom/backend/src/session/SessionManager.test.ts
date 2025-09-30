import type { SessionData, Store } from 'express-session';
import { beforeEach, describe, expect, it } from 'vitest';
import { createSessionMemoryStore } from './middleware.js';
import type { Session } from './payload.js';
import { SessionManager } from './SessionManager.js';

const SESSION_ID = '4a6786f6-76b7-44b6-9c72-a5f79ad344ec';

describe('SessionManager', () => {
  describe('instance', () => {
    let sessionManager: SessionManager;
    let store: Store;

    beforeEach(() => {
      store = createSessionMemoryStore();

      sessionManager = new SessionManager({
        monitoring: {
          logger: {
            info: () => {},
            error: () => {},
          },
        },
        secret: 'this-is-a-secret-2',
        store,
      });
    });

    describe('extractSessionFromHeaders', () => {
      it('extracts a session from a Cookie header', async () => {
        await new Promise<void>((resolve, reject) => {
          store.set(
            SESSION_ID,
            {
              auth: {
                codeVerifier: 'abc',
                stage: 'auth-callback',
              },
              authType: 'oidc',
              cookie: {
                originalMaxAge: null,
              },
            } satisfies Session & { cookie: unknown } as SessionData,
            (err) => {
              if (err) return reject(err);
              resolve();
            },
          );
        });

        const result = await sessionManager.extractSessionFromHeaders({
          Cookie:
            'test=123;s4spar=s%3A4a6786f6-76b7-44b6-9c72-a5f79ad344ec.%2BzgyNtwcuiuZm%2BgiVWvZoShobLVCkrpJTM%2BDZPw0esY',
        });

        expect(result.success).toEqual(true);
      });
    });
  });
});
