import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { AuthManager } from '../../auth/AuthManager.js';
import { validateWorkRoomToken } from '../../auth/sema4OIDC.js';
import type { Configuration } from '../../configuration.js';
import {
  type ErrorResponse,
  type ExpressNextFunction,
  type ExpressRequest,
  type ExpressResponse,
} from '../../interfaces.js';
import { extractRoutePermissions } from './helpers/permissions.js';
import type { Permission } from '../../auth/permissions.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import { extractHeadersFromRequest } from '../../utils/request.js';
import type { Result } from '../../utils/result.js';

const getAuthorizationHeaderValue = (
  headers: Record<string, string>,
): [value: string, header: 'sec-websocket-protocol' | 'authorization'] | [value: null] => {
  if (headers['sec-websocket-protocol']) {
    return [headers['sec-websocket-protocol'].replace(/^bearer[,\s]+/i, 'Bearer '), 'sec-websocket-protocol'];
  }

  return headers['authorization'] ? [headers['authorization'], 'authorization'] : [null];
};

export const handleSema4OIDCAuthCheck = async ({
  authentication,
  authManager,
  configuration,
  monitoring,
  next,
  req,
  res,
}: {
  authentication: 'with-permissions-check' | 'without-permissions-check';
  authManager: AuthManager;
  configuration: Configuration;
  monitoring: MonitoringContext;
  next: ExpressNextFunction;
  req: ExpressRequest;
  res: ExpressResponse;
}) => {
  if (!res.locals.tenantId) {
    monitoring.logger.error('Failed processing OIDC authentication checks: No tenant ID available', {
      requestMethod: req.method,
      requestUrl: req.originalUrl,
    });

    return res.status(401).json({ error: { code: 'unauthorized', message: 'Unauthorized' } } satisfies ErrorResponse);
  }

  const permissions =
    authentication === 'without-permissions-check'
      ? []
      : await extractRoutePermissions({ configuration, monitoring, req });

  if (permissions === null) {
    return res.status(401).json({ error: { code: 'unauthorized', message: 'Unauthorized' } } satisfies ErrorResponse);
  }

  const userIdentityResult = await extractSema4OIDCUserIdentity({
    authManager,
    configuration,
    headers: extractHeadersFromRequest(req.headers),
    monitoring,
    permissions,
  });

  if (!userIdentityResult.success) {
    switch (userIdentityResult.error.code) {
      case 'unauthorized':
        return res
          .status(401)
          .json({ error: { code: 'unauthorized', message: 'Unauthorized' } } satisfies ErrorResponse);
      case 'forbidden':
        return res.status(403).json({ error: { code: 'forbidden', message: 'Forbidden' } } satisfies ErrorResponse);

      default:
        exhaustiveCheck(userIdentityResult.error);
    }
  }

  res.locals.authSub = userIdentityResult.data.userId;

  return next();
};

export const extractSema4OIDCUserIdentity = async ({
  authManager,
  configuration,
  headers,
  monitoring,
  permissions,
}: {
  authManager: AuthManager;
  configuration: Configuration;
  headers: Record<string, string>;
  monitoring: MonitoringContext;
  permissions: Array<Permission>;
}): Promise<
  Result<
    {
      userId: string;
    },
    | {
        code: 'unauthorized';
        message: string;
      }
    | {
        code: 'forbidden';
        message: string;
      }
  >
> => {
  const [authHeaderValue, ...other] = getAuthorizationHeaderValue(headers);

  if (!authHeaderValue) {
    monitoring.logger.error('OIDC authentication attempted but no header found');

    return {
      success: false,
      error: {
        code: 'unauthorized',
        message: 'Authentication required but no header found',
      },
    };
  }

  const [headerName] = other;

  const [authType, token] = authHeaderValue.trim().split(/\s+/);
  if (authType.toLowerCase() !== 'bearer') {
    monitoring.logger.info('OIDC authentication attempted but an invalid header was provided', {
      errorMessage: `Invalid OIDC authorization header: ${headerName}`,
    });

    return {
      success: false,
      error: {
        code: 'unauthorized',
        message: 'OIDC authentication attempted but an invalid header was provided',
      },
    };
  }

  const validatedTokenResult = await validateWorkRoomToken(
    {
      authManager,
      configuration,
      permissions,
    },
    {
      tenantId: configuration.tenant.tenantId,
      encodedToken: token,
    },
  );

  if (!validatedTokenResult.success) {
    monitoring.logger.error('Failed to validate OIDC token', {
      errorName: validatedTokenResult.error.code,
      errorMessage: validatedTokenResult.error.message,
    });

    return {
      success: false,
      error: {
        code: 'forbidden',
        message: `OIDC token validation failed: ${validatedTokenResult.error.message}`,
      },
    };
  }

  return {
    success: true,
    data: {
      userId: validatedTokenResult.data.userId,
    },
  };
};
