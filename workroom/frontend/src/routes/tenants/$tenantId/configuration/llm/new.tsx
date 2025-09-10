import { createFileRoute, useNavigate, useRouter } from '@tanstack/react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from '@sema4ai/components';

import { NewLLMDialog } from '~/components/platforms/llms/components/NewLLMDialog';

export const Route = createFileRoute('/tenants/$tenantId/configuration/llm/new')({
  loader: async ({ params: { tenantId } }) => {
    return { tenantId };
  },
  component: View,
});

function View() {
  const navigate = useNavigate();
  const router = useRouter();
  const { tenantId } = Route.useParams();
  const queryClient = useQueryClient();
  const { addSnackbar } = useSnackbar();

  const onCloseMutation = useMutation({
    mutationFn: async (platformId?: string) => {
      if (platformId) {
        await queryClient.invalidateQueries({ queryKey: ['platforms', tenantId] });
        await router.invalidate();
        addSnackbar({
          message: 'LLM created successfully',
          variant: 'success',
        });
      }
      navigate({ to: '..', params: { tenantId } });
    },
  });

  return <NewLLMDialog onClose={(platformId?: string) => onCloseMutation.mutate(platformId)} open />;
}
