import { createFileRoute } from '@tanstack/react-router';
import { CreateApiKeyDialog } from '~/components/apiKeys/CreateApiKeyDialog';

export const Route = createFileRoute('/tenants/$tenantId/configuration/api-keys/new')({
  component: View,
});

function View() {
  const { tenantId } = Route.useParams();

  return <CreateApiKeyDialog tenantId={tenantId} />;
}
