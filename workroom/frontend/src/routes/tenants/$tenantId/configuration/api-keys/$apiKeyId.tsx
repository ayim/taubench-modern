import { createFileRoute } from '@tanstack/react-router';
import { Progress } from '@sema4ai/components';
import { EditApiKeyDialog } from '~/components/apiKeys/EditApiKeyDialog';
import { trpc } from '~/lib/trpc';

export const Route = createFileRoute('/tenants/$tenantId/configuration/api-keys/$apiKeyId')({
  component: View,
});

function View() {
  const { tenantId, apiKeyId } = Route.useParams();
  const { data: apiKeyData, isLoading } = trpc.apiKeys.get.useQuery({ id: apiKeyId });

  if (isLoading) {
    return <Progress variant="page" />;
  }

  if (apiKeyData) {
    return <EditApiKeyDialog apiKey={apiKeyData} tenantId={tenantId} />;
  }
}
