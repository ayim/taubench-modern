import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import { extractRoutePermissions } from './helpers/permissions.js';
import { upsertSnowflakeUser } from '../../auth/utils/snowflakeUserRegistration.js';
import type { Configuration } from '../../configuration.js';
import type { DatabaseClient } from '../../database/DatabaseClient.js';
import type { UserRole } from '../../database/types/user.js';
import type { ErrorResponse, ExpressNextFunction, ExpressRequest, ExpressResponse } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import type { SessionManager } from '../../session/sessionManager.js';
import { extractHeadersFromRequest } from '../../utils/request.js';
import type { Result } from '../../utils/result.js';
import { SNOWFLAKE_AUTH_HEADER, SNOWFLAKE_AUTHORITY } from '../../utils/snowflake.js';

export type SnowflakeUserIdentityResult = Result<
  {
    userId: string;
    userRole: UserRole;
  },
  | {
      code: 'unauthorized';
      message: string;
    }
  | {
      code: 'forbidden';
      message: string;
    }
  | {
      code: 'misconfigured';
      message: string;
    }
>;

export const createSnowflakeImplicitSessionMiddleware = ({
  configuration,
  database,
  monitoring,
  sessionManager,
}: {
  configuration: Configuration;
  database: DatabaseClient;
  monitoring: MonitoringContext;
  sessionManager: SessionManager;
}) => {
  if (configuration.auth.type !== 'snowflake') {
    return (_req: ExpressRequest, _res: ExpressResponse, next: ExpressNextFunction) => {
      next();
    };
  }

  return async (req: ExpressRequest, res: ExpressResponse, next: ExpressNextFunction) => {
    const accepts = req.header('Accept') ?? '';
    if (!accepts.includes('text/html')) {
      // Only do the processing for HTML/main pages, so we don't end up hitting
      // the database excessively
      return next();
    }

    const headers = extractHeadersFromRequest(req.headers);

    const userIdentityResult = await processImplicitSnowflakeUserIdentity({
      database,
      headers,
      monitoring,
    });
    if (!userIdentityResult.success) {
      monitoring.logger.error('Failed processing implicit Snowflake user identity', {
        errorMessage: userIdentityResult.error.message,
        errorName: userIdentityResult.error.code,
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });

      return res.status(401).json({
        error: {
          code: 'unauthorized',
          message: 'Unauthorized',
        },
      } satisfies ErrorResponse);
    }

    const setResult = await sessionManager.setSessionOnRequest(req, {
      auth: {
        stage: 'authenticated',
        userId: userIdentityResult.data.userId,
        userRole: userIdentityResult.data.userRole,
      },
      authType: 'snowflake',
    });
    if (!setResult.success) {
      monitoring.logger.error('Failed to set Snowflake session', {
        errorMessage: setResult.error.message,
        errorName: setResult.error.code,
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });

      return res.status(500).json({
        error: {
          code: 'internal_error',
          message: 'Internal server error',
        },
      } satisfies ErrorResponse);
    }

    next();
  };
};

export const handleSnowflakeAuthCheck = async ({
  authentication,
  configuration,
  monitoring,
  next,
  req,
  res,
  sessionManager,
}: {
  authentication: 'with-permissions-check' | 'without-permissions-check';
  configuration: Configuration;
  monitoring: MonitoringContext;
  next: ExpressNextFunction;
  req: ExpressRequest;
  res: ExpressResponse;
  sessionManager: SessionManager;
}) => {
  const permissions =
    authentication === 'without-permissions-check'
      ? []
      : await extractRoutePermissions({ configuration, monitoring, req });

  if (permissions === null) {
    return res.status(401).json({ error: { code: 'unauthorized', message: 'Unauthorized' } } satisfies ErrorResponse);
  }

  const userIdentityResult = await extractSnowflakeUserIdentity({
    headers: extractHeadersFromRequest(req.headers),
    monitoring,
    sessionManager,
  });

  if (!userIdentityResult.success) {
    switch (userIdentityResult.error.code) {
      case 'unauthorized':
        return res
          .status(401)
          .json({ error: { code: 'unauthorized', message: 'Unauthorized' } } satisfies ErrorResponse);
      case 'forbidden':
        await sessionManager.clearSessionForRequest(req);
        return res.status(403).json({
          error: {
            code: 'forbidden',
            message: 'Forbidden',
          },
        } satisfies ErrorResponse);
      case 'misconfigured':
        return res.status(409).send('Conflict: Invalid session state');

      default:
        exhaustiveCheck(userIdentityResult.error);
    }
  }

  res.locals.authSub = userIdentityResult.data.userId;

  return next();
};

export const extractSnowflakeUserIdentity = async ({
  headers,
  monitoring,
  sessionManager,
}: {
  headers: Record<string, string>;
  monitoring: MonitoringContext;
  sessionManager: SessionManager;
}): Promise<SnowflakeUserIdentityResult> => {
  const sessionResult = await sessionManager.extractSessionFromHeaders(headers);
  if (!sessionResult.success) {
    switch (sessionResult.error.code) {
      case 'invalid_session':
        monitoring.logger.error('Snowflake authentication attempted but an invalid session was provided', {
          errorName: sessionResult.error.code,
          errorMessage: sessionResult.error.message,
        });

        return {
          success: false,
          error: {
            code: 'forbidden',
            message: 'Session validation failed',
          },
        };
      case 'no_session':
        monitoring.logger.info('Snowflake authentication attempted but no session was found', {
          errorName: sessionResult.error.code,
          errorMessage: sessionResult.error.message,
        });

        return {
          success: false,
          error: {
            code: 'unauthorized',
            message: 'No session',
          },
        };

      default:
        exhaustiveCheck(sessionResult.error.code);
    }
  }

  if (!sessionResult.data) {
    monitoring.logger.error('Snowflake authentication attempted but an empty session was provided');

    return {
      success: false,
      error: {
        code: 'forbidden',
        message: 'Session validation failed due to incomplete login',
      },
    };
  }

  if (sessionResult.data.authType !== 'snowflake') {
    monitoring.logger.error('Snowflake authentication attempted but session authentication was not in Snowflake mode', {
      errorMessage: `Bad auth type for session: ${sessionResult.data.authType}`,
    });

    return {
      success: false,
      error: {
        code: 'forbidden',
        message: 'Session validation failed due to an invalid session',
      },
    };
  }

  if (sessionResult.data.auth.stage !== 'authenticated') {
    monitoring.logger.error('Snowflake authentication attempted but an incomplete session was provided');

    return {
      success: false,
      error: {
        code: 'misconfigured',
        message: 'Session in invalid state for this platform',
      },
    };
  }

  return {
    success: true,
    data: {
      userId: sessionResult.data.auth.userId,
      userRole: sessionResult.data.auth.userRole,
    },
  };
};

const processImplicitSnowflakeUserIdentity = async ({
  database,
  headers,
  monitoring,
}: {
  database: DatabaseClient;
  headers: Record<string, string>;
  monitoring: MonitoringContext;
}): Promise<SnowflakeUserIdentityResult> => {
  const authHeaderValue = headers[SNOWFLAKE_AUTH_HEADER.toLowerCase()];
  if (!authHeaderValue) {
    monitoring.logger.error('No header found for Snowflake authentication');

    return {
      success: false,
      error: {
        code: 'unauthorized',
        message: 'No header found for Snowflake authentication',
      },
    };
  }

  const userIdentityResult = await database.findUserIdentity({
    authority: SNOWFLAKE_AUTHORITY,
    identityValue: authHeaderValue,
    type: 'snowflake_user_header',
  });
  if (!userIdentityResult.success) {
    monitoring.logger.error('Failed fetching user identity for Snowflake user header', {
      errorMessage: userIdentityResult.error.message,
      errorName: userIdentityResult.error.code,
    });

    return {
      success: false,
      error: {
        code: 'unauthorized',
        message: 'Failed fetching user identity for Snowflake user header',
      },
    };
  }
  if (!userIdentityResult.data) {
    const upsertResult = await upsertSnowflakeUser({
      database,
      monitoring,
      snowflake: {
        currentUserContextHeader: authHeaderValue,
      },
    });
    if (!upsertResult.success) {
      monitoring.logger.error('Failed updating Snowflake user record', {
        errorMessage: upsertResult.error.message,
        errorName: upsertResult.error.code,
      });

      return {
        success: false,
        error: {
          code: 'unauthorized',
          message: 'Failed fetching user identity for Snowflake user header',
        },
      };
    }

    return {
      success: true,
      data: {
        userId: upsertResult.data.userId,
        userRole: upsertResult.data.userRole,
      },
    };
  }

  const userResult = await database.getUser({ id: userIdentityResult.data.user_id });
  if (!userResult.success) {
    monitoring.logger.error('Failed fetching user for Snowflake identity', {
      errorMessage: userResult.error.message,
      errorName: userResult.error.code,
    });

    return {
      success: false,
      error: {
        code: 'unauthorized',
        message: 'Failed fetching user for Snowflake identity',
      },
    };
  }

  return {
    success: true,
    data: {
      userId: userResult.data.id,
      userRole: userResult.data.role,
    },
  };
};
