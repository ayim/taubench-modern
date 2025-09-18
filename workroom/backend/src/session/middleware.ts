import { randomUUID } from 'node:crypto';
import session, { type MemoryStore as ExpressSessionMemoryStore } from 'express-session';
import createMemoryStore from 'memorystore';
import type { Configuration } from '../configuration.js';
import type { ExpressNextFunction, ExpressRequest, ExpressResponse } from '../interfaces.js';
import type { SessionManager } from './SessionManager.js';
import type { MonitoringContext } from '../monitoring/index.js';

const SESSION_PRUNE_PERIOD = 1 * 60 * 60 * 1000; // 1 hour

export const createSessionMiddleware = ({
  configuration,
  monitoring,
  sessionManager,
}: {
  configuration: Configuration;
  monitoring: MonitoringContext;
  sessionManager: SessionManager;
}) => {
  if (!configuration.session) {
    monitoring.logger.info('Sessions disabled');

    return (_req: ExpressRequest, _res: ExpressResponse, next: ExpressNextFunction) => {
      next();
    };
  }

  monitoring.logger.info('Sessions enabled');

  return session({
    secret: configuration.session.secret,
    resave: false,
    name: sessionManager.sessionCookieName,
    saveUninitialized: false,
    store: sessionManager.store,
    genid: () => randomUUID(),
    cookie: {
      maxAge: configuration.session.cookieMaxAgeMs,
      secure: configuration.allowInsecureRequests ? false : true,
    },
  });
};

export const createSessionMemoryStore = (): ExpressSessionMemoryStore => {
  const MemoryStore = createMemoryStore(session);

  return new MemoryStore({
    checkPeriod: SESSION_PRUNE_PERIOD,
  });
};
