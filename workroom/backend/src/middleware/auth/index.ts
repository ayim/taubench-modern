import { exhaustiveCheck } from '@sema4ai/robocloud-shared-utils';
import type { NextFunction, Request, Response } from 'express';
import { extractGoogleUserIdentity, handleGoogleAuthCheck } from './google.js';
import type { Configuration } from '../../configuration.js';
import type { MonitoringContext } from '../../monitoring/index.js';
import type { Result } from '../../utils/result.js';

export const createAuthMiddleware =
  ({ configuration, monitoring }: { configuration: Configuration; monitoring: MonitoringContext }) =>
  async (req: Request, res: Response, next: NextFunction) => {
    switch (configuration.auth.type) {
      case 'none':
        return next();
      case 'google':
        return handleGoogleAuthCheck({ monitoring, next, req, res });

      default:
        exhaustiveCheck(configuration.auth);
    }
  };

export const extractAuthenticatedUserIdentity = ({
  configuration,
  headers,
  monitoring,
}: {
  configuration: Configuration;
  headers: Record<string, string>;
  monitoring: MonitoringContext;
}): Result<
  {
    userId: string | null;
  },
  {
    code: 'unauthorized';
    message: string;
  }
> => {
  switch (configuration.auth.type) {
    case 'none':
      return {
        success: true,
        data: {
          userId: null,
        },
      };
    case 'google':
      return extractGoogleUserIdentity({ headers, monitoring });

    default:
      exhaustiveCheck(configuration.auth);
  }
};
