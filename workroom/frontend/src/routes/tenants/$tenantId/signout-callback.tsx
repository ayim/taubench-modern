import { Navigate, createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/signout-callback')({
  component: View,
});

function View() {
  const { tenantId } = Route.useParams();
  return <Navigate to="/tenants/$tenantId/home" params={{ tenantId }} />;
}
