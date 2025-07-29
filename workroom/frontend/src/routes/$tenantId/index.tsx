import { createFileRoute, Navigate } from '@tanstack/react-router';

export const Route = createFileRoute('/$tenantId/')({
  component: View,
});

function View() {
  const { tenantId } = Route.useParams();
  return <Navigate to="/$tenantId/home" params={{ tenantId }} />;
}
