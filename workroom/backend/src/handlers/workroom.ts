import type { Request, Response } from 'express';
import type { Configuration, WorkroomMeta } from '../configuration.js';
import { createProxyHandler } from './agents.js';
import type { ErrorResponse } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { safeParseUrl } from '../utils/url.js';

export const createGetWorkroomMeta =
  ({ configuration, monitoring }: { configuration: Configuration; monitoring: MonitoringContext }) =>
  (req: Request, res: Response) => {
    // Features are configured in 3 different ways:
    //  1. SPAR-based, encoded in Configuration
    //  2. Bypassed meta endpoint on ACE (via ingress rules), returning overridden
    //     features from an internal route (this handler is never requested)
    //  3. Features URL redirect on SPCS, pointing to an endpoint that returns
    //     overridden features from an internal route

    if (configuration.featuresUrl) {
      const targetMetaUrlResult = safeParseUrl(configuration.featuresUrl);
      if (!targetMetaUrlResult.success) {
        monitoring.logger.error('Failed generating workroom meta: Invalid features URL', {
          errorMessage: targetMetaUrlResult.error.message,
          errorName: targetMetaUrlResult.error.code,
        });

        return res.status(500).json({
          error: { code: 'internal_error', message: 'Invalid configuration' },
        } satisfies ErrorResponse);
      }

      const targetMetaPath = targetMetaUrlResult.data.pathname;

      const baseURL = new URL(targetMetaUrlResult.data);
      baseURL.pathname = '';

      return createProxyHandler({
        apiType: 'private',
        configuration,
        monitoring,
        rewriteAgentServerPath: () => targetMetaPath,
        skipAuthentication: true,
        targetBaseUrl: baseURL.toString(),
      })(req, res);
    }

    res.json(configuration.workroomMeta satisfies WorkroomMeta);
  };
