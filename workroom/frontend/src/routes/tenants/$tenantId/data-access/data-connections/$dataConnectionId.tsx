import { DataConnectionConfiguration } from '@sema4ai/spar-ui';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/data-access/data-connections/$dataConnectionId')({
  component: RouteComponent,
});

function RouteComponent() {
  return <DataConnectionConfiguration />;
}
