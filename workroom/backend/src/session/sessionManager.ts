import { exhaustiveCheck, type Result } from '@sema4ai/shared-utils';
import type { Store } from 'express-session';
import type { ExpressRequest } from '../interfaces.js';
import { DatabaseSessionStore } from './DatabaseSessionStore.js';
import { HTTPSessionManager } from './HTTPSessionManager.js';
import type { Session } from './payload.js';
import type { Configuration } from '../configuration.js';
import { SnowflakeSessionManager } from './SnowflakeSessionManager.js';
import type { DatabaseClient } from '../database/DatabaseClient.js';
import type { MonitoringContext } from '../monitoring/index.js';

export type ExtractSessionResult = Result<Session, { code: 'invalid_session' | 'no_session'; message: string }>;

export interface SessionManager {
  clearSessionForRequest: (req: ExpressRequest) => Promise<Result<void>>;
  destroySessionForId: (sessionId: string) => Promise<Result<void>>;
  extractSessionFromHeaders: (headers: Headers | Record<string, string>) => Promise<ExtractSessionResult>;
  extractSessionFromRequest: (req: ExpressRequest) => Promise<ExtractSessionResult>;
  sessionCookieName?: string;
  setSessionOnRequest: (req: ExpressRequest, session: Session) => Promise<Result<void>>;
  store?: Store;
}

export const createSessionManager = ({
  configuration,
  database,
  monitoring,
  secret,
}: {
  configuration: Configuration;
  database: DatabaseClient;
  monitoring: MonitoringContext;
  secret: string;
}): SessionManager => {
  const store = new DatabaseSessionStore({
    database,
    sessionExpirySeconds: configuration.sessionCookieMaxAgeMs / 1000,
  });

  switch (configuration.auth.type) {
    case 'snowflake':
      return new SnowflakeSessionManager({
        monitoring,
        store,
      });

    case 'none':
    case 'oidc':
      return new HTTPSessionManager({
        monitoring,
        secret,
        store,
        tenantId: configuration.tenant.tenantId,
      });

    default:
      exhaustiveCheck(configuration.auth);
  }
};
