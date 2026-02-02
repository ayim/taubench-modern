import { SemanticDataConfiguration } from '~/components/SemanticData/SemanticDataConfiguration';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/data-access/semantic-data/')({
  component: RouteComponent,
});

function RouteComponent() {
  return <SemanticDataConfiguration onClose={() => {}} />;
}
