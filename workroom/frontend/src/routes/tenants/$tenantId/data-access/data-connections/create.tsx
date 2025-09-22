import { createFileRoute } from '@tanstack/react-router';
import { DataConnectionConfiguration } from '@sema4ai/spar-ui';

export const Route = createFileRoute('/tenants/$tenantId/data-access/data-connections/create')({
  component: RouteComponent,
});

function RouteComponent() {
  return <DataConnectionConfiguration />;
}
