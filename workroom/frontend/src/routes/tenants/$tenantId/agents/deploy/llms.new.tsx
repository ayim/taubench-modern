import { createFileRoute, useParams } from '@tanstack/react-router';
import { NewLLMDialog } from '~/components/platforms/llms/components/NewLLMDialog';

export const Route = createFileRoute('/tenants/$tenantId/agents/deploy/llms/new')({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = Route.useNavigate();
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });

  return (
    <NewLLMDialog onClose={() => navigate({ to: '/tenants/$tenantId/agents/deploy', params: { tenantId } })} open />
  );
}
