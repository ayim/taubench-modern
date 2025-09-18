import type { Configuration } from '../configuration.js';
import type { ErrorResponse, ExpressNextFunction, ExpressRequest, ExpressResponse } from '../interfaces.js';
import type { MonitoringContext } from '../monitoring/index.js';
import { TenantRequestParameters } from '../utils/schemas.js';

export const createTenantExtractionMiddleware =
  ({ configuration, monitoring }: { configuration: Configuration; monitoring: MonitoringContext }) =>
  (req: ExpressRequest, res: ExpressResponse, next: ExpressNextFunction) => {
    const tenantParametersResult = TenantRequestParameters.safeParse(req.params);
    if (!tenantParametersResult.success) {
      monitoring.logger.error('Failed parsing tenant parameters', {
        error: tenantParametersResult.error,
      });

      return res
        .status(403)
        .json({ error: { code: 'invalid_request', message: 'Bad Request' } } satisfies ErrorResponse);
    }

    if (tenantParametersResult.data.tenantId !== configuration.tenant.tenantId) {
      monitoring.logger.error('Bad tenant-prefixed path: Tenant ID did not match the statically expected value', {
        requestMethod: req.method,
        requestUrl: req.originalUrl,
        tenantId: tenantParametersResult.data.tenantId,
      });

      return res.status(404).json({ error: { code: 'not_found', message: 'Not found' } } satisfies ErrorResponse);
    }

    res.locals.tenantId = tenantParametersResult.data.tenantId;

    next();
  };
