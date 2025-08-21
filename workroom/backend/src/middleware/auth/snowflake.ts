import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { ExpressNextFunction, ExpressRequest, ExpressResponse } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import { extractHeadersFromRequest } from '../../utils/request.js';
import type { Result } from '../../utils/result.js';

export type SnowflakeUserIdentityResult = Result<
  {
    userId: string;
  },
  {
    code: 'unauthorized';
    message: string;
  }
>;

/**
 * Snowflake user identity header
 * @example
 *  "perry@sema4.ai"
 * @example
 *  "perry"
 */
export const SNOWFLAKE_AUTH_HEADER = 'sf-context-current-user';

export const handleSnowflakeAuthCheck = async ({
  monitoring,
  next,
  req,
  res,
}: {
  monitoring: MonitoringContext;
  next: ExpressNextFunction;
  req: ExpressRequest;
  res: ExpressResponse;
}) => {
  const userIdentityResult = extractSnowflakeUserIdentity({
    headers: extractHeadersFromRequest(req.headers),
    monitoring,
  });

  if (!userIdentityResult.success) {
    switch (userIdentityResult.error.code) {
      case 'unauthorized':
        return res.status(401).send('Unauthorized');

      default:
        exhaustiveCheck(userIdentityResult.error.code);
    }
  }

  res.locals.authSub = userIdentityResult.data.userId;

  return next();
};

export const extractSnowflakeUserIdentity = ({
  headers,
  monitoring,
}: {
  headers: Record<string, string>;
  monitoring: MonitoringContext;
}): SnowflakeUserIdentityResult => {
  const authHeaderValue = headers[SNOWFLAKE_AUTH_HEADER.toLowerCase()];
  if (!authHeaderValue) {
    monitoring.logger.error('Snowflake authentication required but no header found');

    return {
      success: false,
      error: {
        code: 'unauthorized',
        message: 'Snowflake authentication required but no header found',
      },
    };
  }

  return {
    success: true,
    data: {
      userId: authHeaderValue,
    },
  };
};
