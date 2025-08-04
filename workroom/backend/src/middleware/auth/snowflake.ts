import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { Request, Response, NextFunction } from 'express';
import type { MonitoringContext } from '../../monitoring/index.js';
import { REQUEST_AUTH_ID_KEY } from '../../utils/auth.js';
import { extractHeadersFromRequest } from '../../utils/request.js';
import type { Result } from '../../utils/result.js';

/**
 * Snowflake user identity header
 * @example
 *  "perry@sema4.ai"
 * @example
 *  "perry"
 */
const SNOWFLAKE_AUTH_HEADER = 'sf-context-current-user';

export const handleSnowflakeAuthCheck = async ({
  monitoring,
  next,
  req,
  res,
}: {
  monitoring: MonitoringContext;
  next: NextFunction;
  req: Request;
  res: Response;
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

  res.locals[REQUEST_AUTH_ID_KEY] = userIdentityResult.data.userId;

  return next();
};

export const extractSnowflakeUserIdentity = ({
  headers,
  monitoring,
}: {
  headers: Record<string, string>;
  monitoring: MonitoringContext;
}): Result<
  {
    userId: string;
  },
  {
    code: 'unauthorized';
    message: string;
  }
> => {
  const authHeaderValue = headers[SNOWFLAKE_AUTH_HEADER.toLowerCase()];
  if (!authHeaderValue) {
    monitoring.logger.error('Snowflake authentication attempted but no header found');

    return {
      success: false,
      error: {
        code: 'unauthorized',
        message: 'Snowflake authentication attempted but no header found',
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
