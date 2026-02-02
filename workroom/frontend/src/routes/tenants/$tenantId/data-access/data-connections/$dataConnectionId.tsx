import { DataConnectionConfiguration } from '~/components/DataConnection/DataConnectionConfiguration';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/data-access/data-connections/$dataConnectionId')({
  component: RouteComponent,
});

function RouteComponent() {
  return <DataConnectionConfiguration />;
}
