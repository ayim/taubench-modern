import { createFileRoute, useNavigate, useParams, useRouter, useRouteContext } from '@tanstack/react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { successToast } from '~/utils/toasts';
import { NewLLMDialog } from '~/components/platforms/llms/components/NewLLMDialog';

export const Route = createFileRoute('/tenants/$tenantId/settings/llm/new')({
  loader: async ({ params: { tenantId } }) => {
    return { tenantId };
  },
  component: View,
});

function View() {
  const navigate = useNavigate();
  const router = useRouter();
  const { tenantId } = useParams({ from: '/tenants/$tenantId/settings/llm/new' });
  useRouteContext({ from: '/tenants/$tenantId' });
  const queryClient = useQueryClient();

  const onCloseMutation = useMutation({
    mutationFn: async (platformId?: string) => {
      if (platformId) {
        await queryClient.invalidateQueries({ queryKey: ['platforms', tenantId] });
        await router.invalidate();
        successToast('LLM created successfully');
      }
      navigate({ to: '..', params: { tenantId } });
    },
  });

  return <NewLLMDialog onClose={(platformId?: string) => onCloseMutation.mutate(platformId)} open />;
}
