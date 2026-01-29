import { createFileRoute } from '@tanstack/react-router';
import { DataConnectionConfiguration } from '~/components/DataConnection/DataConnectionConfiguration';

export const Route = createFileRoute('/tenants/$tenantId/data-access/data-connections/create')({
  component: RouteComponent,
});

function RouteComponent() {
  return <DataConnectionConfiguration />;
}
