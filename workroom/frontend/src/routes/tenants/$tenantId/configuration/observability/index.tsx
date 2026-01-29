import { createFileRoute } from '@tanstack/react-router';
import { GlobalObservabilityConfiguration } from '~/components/Integrations/GlobalObservabilityConfiguration';

export const Route = createFileRoute('/tenants/$tenantId/configuration/observability/')({
  component: RouteComponent,
});

function RouteComponent() {
  return <GlobalObservabilityConfiguration />;
}
