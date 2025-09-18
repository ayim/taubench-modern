import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { ErrorResponse, ExpressNextFunction, ExpressRequest, ExpressResponse } from '../../interfaces.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import { extractHeadersFromRequest } from '../../utils/request.js';
import type { Result } from '../../utils/result.js';

export type GoogleUserIdentityResult = Result<
  {
    userId: string;
  },
  {
    code: 'unauthorized';
    message: string;
  }
>;

/**
 * Google authentication header, provided when auth is enabled for GCP
 * hosted applications.
 * @example
 *  "accounts.google.com:109000000000000000000"
 */
export const GOOGLE_AUTH_HEADER = 'X-Goog-Authenticated-User-ID';

export const handleGoogleAuthCheck = async ({
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
  const userIdentityResult = extractGoogleUserIdentity({
    headers: extractHeadersFromRequest(req.headers),
    monitoring,
  });

  if (!userIdentityResult.success) {
    switch (userIdentityResult.error.code) {
      case 'unauthorized':
        return res
          .status(401)
          .json({ error: { code: 'unauthorized', message: 'Unauthorized' } } satisfies ErrorResponse);

      default:
        exhaustiveCheck(userIdentityResult.error.code);
    }
  }

  // @TODO: User Id is no longer identifiable as a Google ID.. this should
  // be addressed, but it should not contain a colon due to the string joining
  // in the agent server token signing process.
  res.locals.authSub = userIdentityResult.data.userId;

  return next();
};

export const extractGoogleUserIdentity = ({
  headers,
  monitoring,
}: {
  headers: Record<string, string>;
  monitoring: MonitoringContext;
}): GoogleUserIdentityResult => {
  const authHeaderValue = headers[GOOGLE_AUTH_HEADER.toLowerCase()];
  if (!authHeaderValue) {
    monitoring.logger.error('Google authentication required but no header found');

    return {
      success: false,
      error: {
        code: 'unauthorized',
        message: 'Google authentication required but no header found',
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
