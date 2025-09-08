import { Outlet, createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId')({
  component: View,
});

function View() {
  return <Outlet />;
}
