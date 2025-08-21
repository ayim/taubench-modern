import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import { parseAgentRequest } from '../../api/parsers.js';
import { getRouteBehaviour } from '../../api/routing.js';
import { validateWorkRoomToken, type GetACEUser, type Permission } from '../../auth/oidc.js';
import type { Configuration } from '../../configuration.js';
import { type ExpressNextFunction, type ExpressRequest, type ExpressResponse } from '../../interfaces.js';
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

export const handleOIDCAuthCheck = async ({
  authentication,
  configuration,
  getACEUser,
  monitoring,
  next,
  req,
  res,
}: {
  authentication: 'with-permissions-check' | 'without-permissions-check';
  configuration: Configuration;
  getACEUser: GetACEUser;
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

    return res.status(401).send('Unauthorized');
  }

  const permissions: Array<Permission> | null = (() => {
    if (authentication === 'without-permissions-check') {
      return [];
    }

    authentication satisfies 'with-permissions-check';

    // @TODO: Move replace to option
    const requestPathWithQueryStringParameters = req.originalUrl.replace(/^\/tenants\/[^/]+\/agents/, '');

    const route = parseAgentRequest({
      method: req.method,
      path: requestPathWithQueryStringParameters,
    });
    if (!route) {
      monitoring.logger.error('Route is invalid for OIDC authentication', {
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });

      return null;
    }

    const routeBehaviour = getRouteBehaviour({
      configuration,
      route,
      tenantId: configuration.tenant.tenantId,
      userId: '', // We don't use the signer for this result, so the user ID isn't required
    });

    if (!routeBehaviour.isAllowed) {
      monitoring.logger.error('Failed processing OIDC authentication: Route is disallowed', {
        requestMethod: req.method,
        requestUrl: req.originalUrl,
      });

      return null;
    }

    return routeBehaviour.permissions;
  })();

  if (permissions === null) {
    return res.status(401).send('Unauthorized');
  }

  const userIdentityResult = await extractOIDCUserIdentity({
    configuration,
    getACEUser,
    headers: extractHeadersFromRequest(req.headers),
    monitoring,
    permissions,
  });

  if (!userIdentityResult.success) {
    switch (userIdentityResult.error.code) {
      case 'unauthorized':
        return res.status(401).send('Unauthorized');
      case 'forbidden':
        return res.status(403).send('Forbidden');

      default:
        exhaustiveCheck(userIdentityResult.error);
    }
  }

  // @TODO: User Id is no longer identifiable as a Google ID.. this should
  // be addressed, but it should not contain a colon due to the string joining
  // in the agent server token signing process.
  res.locals.authSub = userIdentityResult.data.userId;

  return next();
};

export const extractOIDCUserIdentity = async ({
  configuration,
  getACEUser,
  headers,
  monitoring,
  permissions,
}: {
  configuration: Configuration;
  getACEUser: GetACEUser;
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
      configuration,
      getACEUser,
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
