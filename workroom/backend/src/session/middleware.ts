import { randomUUID } from 'node:crypto';
import session from 'express-session';
import type { Configuration } from '../configuration.js';
import type { ExpressNextFunction, ExpressRequest, ExpressResponse } from '../interfaces.js';
import type { SessionManager } from './sessionManager.js';
import type { MonitoringContext } from '../monitoring/index.js';

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

  if (!sessionManager.sessionCookieName || !sessionManager.store) {
    monitoring.logger.info('Sessions disabled via manager');

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
      httpOnly: true,
      maxAge: configuration.sessionCookieMaxAgeMs,
      secure: configuration.allowInsecureRequests ? false : true,
      sameSite: 'lax',
    },
  });
};
