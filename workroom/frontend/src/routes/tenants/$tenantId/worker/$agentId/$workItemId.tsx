import { createFileRoute, Outlet } from '@tanstack/react-router';
import { getPreferenceKey, setUserPreferenceId } from '~/utils';

export const Route = createFileRoute('/tenants/$tenantId/worker/$agentId/$workItemId')({
  loader: async ({ params: { agentId, workItemId } }) => {
    setUserPreferenceId(getPreferenceKey({ agentId }), workItemId);
  },
  component: RouteComponent,
});

function RouteComponent() {
  return <Outlet />;
}
