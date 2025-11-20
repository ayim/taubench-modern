import { createFileRoute } from '@tanstack/react-router';
import { GlobalObservabilityConfiguration } from '@sema4ai/spar-ui';

export const Route = createFileRoute('/tenants/$tenantId/configuration/observability/')({
  component: RouteComponent,
});

function RouteComponent() {
  return <GlobalObservabilityConfiguration />;
}
