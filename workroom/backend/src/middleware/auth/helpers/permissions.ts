import { parseAgentRequest } from '../../../api/parsers.js';
import { getRouteBehaviour } from '../../../api/routing.js';
import type { Permission } from '../../../auth/permissions.js';
import type { Configuration } from '../../../configuration.js';
import type { ExpressRequest } from '../../../interfaces.js';
import type { MonitoringContext } from '../../../monitoring/index.js';

export const extractRoutePermissions = async ({
  configuration,
  monitoring,
  req,
}: {
  configuration: Configuration;
  monitoring: MonitoringContext;
  req: ExpressRequest;
}): Promise<Array<Permission> | null> => {
  const requestPathWithQueryStringParameters = req.originalUrl.replace(/^\/tenants\/[^/]+\/agents/, '');

  const route = parseAgentRequest({
    method: req.method,
    path: requestPathWithQueryStringParameters,
  });
  if (!route) {
    monitoring.logger.error('Route not found for this method and path', {
      requestMethod: req.method,
      requestUrl: requestPathWithQueryStringParameters,
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
    monitoring.logger.error('Route not allowed', {
      requestMethod: req.method,
      requestUrl: requestPathWithQueryStringParameters,
    });

    return null;
  }

  return routeBehaviour.permissions;
};
