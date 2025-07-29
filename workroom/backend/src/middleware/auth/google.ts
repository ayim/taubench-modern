import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { Request, Response, NextFunction } from 'express';
import type { MonitoringContext } from '../../monitoring/index.js';
import { REQUEST_AUTH_ID_KEY } from '../../utils/auth.js';
import { extractHeadersFromRequest } from '../../utils/request.js';
import type { Result } from '../../utils/result.js';

/**
 * Google authentication header, provided when auth is enabled for GCP
 * hosted applications.
 * @example
 *  "accounts.google.com:109000000000000000000"
 */
const GOOGLE_AUTH_HEADER = 'X-Goog-Authenticated-User-ID';

export const handleGoogleAuthCheck = async ({
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
  const userIdentityResult = extractGoogleUserIdentity({
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

  // @TODO: User Id is no longer identifiable as a Google ID.. this should
  // be addressed, but it should not contain a colon due to the string joining
  // in the agent server token signing process.
  res.locals[REQUEST_AUTH_ID_KEY] = userIdentityResult.data.userId;

  return next();
};

export const extractGoogleUserIdentity = ({
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
  const authHeaderValue = headers[GOOGLE_AUTH_HEADER.toLowerCase()];
  if (!authHeaderValue) {
    monitoring.logger.info('Google authentication attempted but no header found');

    return {
      success: false,
      error: {
        code: 'unauthorized',
        message: 'Google authentication attempted but no header found',
      },
    };
  }

  const [domain, userId] = authHeaderValue.split(':');
  if (domain !== 'accounts.google.com') {
    monitoring.logger.info('Google authentication attempted but an invalid header was provided', {
      errorMessage: `Invalid Google authentication header: ${GOOGLE_AUTH_HEADER} = ${authHeaderValue}`,
    });

    return {
      success: false,
      error: {
        code: 'unauthorized',
        message: 'Google authentication attempted but an invalid header was provided',
      },
    };
  }

  return {
    success: true,
    data: {
      userId,
    },
  };
};
