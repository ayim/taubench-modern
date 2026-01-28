import { Progress } from '@sema4ai/components';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { EditPlatformDialog } from '~/components/platforms/EditPlatformDialog';
import { usePlatformQuery } from '~/queries/platforms';

export const Route = createFileRoute('/tenants/$tenantId/configuration/llm/$platformId')({
  component: View,
});

function View() {
  const navigate = useNavigate();
  const { tenantId, platformId } = Route.useParams();
  const { data: platform, isLoading } = usePlatformQuery({ platformId });

  if (isLoading || !platform) {
    return <Progress variant="page" />;
  }

  return <EditPlatformDialog platform={platform} open onClose={() => navigate({ to: '..', params: { tenantId } })} />;
}
