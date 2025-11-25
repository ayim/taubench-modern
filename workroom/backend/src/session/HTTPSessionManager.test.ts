import session, { type MemoryStore, type SessionData, Store } from 'express-session';
import createMemoryStore from 'memorystore';
import { beforeEach, describe, expect, it } from 'vitest';
import { HTTPSessionManager } from './HTTPSessionManager.js';
import type { Session } from './payload.js';

const SESSION_ID = '4a6786f6-76b7-44b6-9c72-a5f79ad344ec';

const createSessionMemoryStore = (): MemoryStore => {
  const MemoryStore = createMemoryStore(session);
  return new MemoryStore({
    checkPeriod: 1 * 60 * 60 * 1000, // one hour
  });
};

describe('SessionManager', () => {
  describe('instance', () => {
    let sessionManager: HTTPSessionManager;
    let store: Store;

    beforeEach(() => {
      store = createSessionMemoryStore();

      sessionManager = new HTTPSessionManager({
        monitoring: {
          logger: {
            debug: () => {},
            info: () => {},
            error: () => {},
          },
        },
        secret: 'this-is-a-secret-2',
        store,
        tenantId: 'test-tenant',
      });
    });

    it('uses a dynamic tenant-based cookie name', () => {
      expect(sessionManager.sessionCookieName).toEqual('s4spar.test-tenant');
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
            'test=123;s4spar.test-tenant=s%3A4a6786f6-76b7-44b6-9c72-a5f79ad344ec.%2BzgyNtwcuiuZm%2BgiVWvZoShobLVCkrpJTM%2BDZPw0esY',
        });

        expect(result.success).toEqual(true);
      });
    });
  });
});
