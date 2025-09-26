import { SemanticDataConfiguration } from '@sema4ai/spar-ui';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/data-access/semantic-data/')({
  component: RouteComponent,
});

function RouteComponent() {
  return <SemanticDataConfiguration onClose={() => {}} />;
}
