import { Outlet, createFileRoute, useParams, useRouteContext, useRouter } from '@tanstack/react-router';
import { useMemo, useState } from 'react';
import { useMutation, useQueryClient, useSuspenseQuery } from '@tanstack/react-query';
import { Box, Header, Scroll, Dialog, Button } from '@sema4ai/components';
import { LLMsTable, LLMTableItem } from '~/components/platforms/llms/components/LLMsTable';
import { getListPlatformsQueryOptions, type ListPlatformsResponse } from '~/queries/platforms';
import { successToast } from '~/utils/toasts';

export const Route = createFileRoute('/tenants/$tenantId/settings/llm')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { tenantId } }) => {
    await queryClient.ensureQueryData(getListPlatformsQueryOptions({ agentAPIClient, tenantId }));
    return {};
  },
  component: RouteComponent,
});

function RouteComponent() {
  const { tenantId } = useParams({ from: '/tenants/$tenantId/settings/llm' });
  useRouteContext({ from: '/tenants/$tenantId' });
  const router = useRouter();
  const queryClient = useQueryClient();
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const [deleteTarget, setDeleteTarget] = useState<LLMTableItem | null>(null);

  type DeleteMutationVars = { tenantId: string; platformId: string };

  const deleteMutation = useMutation<
    unknown,
    unknown,
    DeleteMutationVars,
    { previousPlatforms?: ListPlatformsResponse; tenantId: string }
  >({
    mutationFn: async ({ tenantId, platformId }: DeleteMutationVars) => {
      await agentAPIClient.agentFetch(tenantId, 'delete', '/api/v2/platforms/{platform_id}', {
        params: { path: { platform_id: platformId } },
        errorMsg: 'Failed to delete LLM',
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['platforms', tenantId] });
      successToast('LLM deleted successfully');
      setDeleteTarget(null);
    },
  });

  const { data } = useSuspenseQuery(getListPlatformsQueryOptions({ agentAPIClient, tenantId }));

  const items = useMemo<LLMTableItem[]>(() => {
    const platforms: ListPlatformsResponse | undefined = data ?? queryClient.getQueryData(['platforms', tenantId]);
    return (platforms || [])
      .filter((p) => Boolean(p.platform_id))
      .map((p) => ({
        id: p.platform_id as string,
        name: p.name,
        provider: p.kind,
        model: Array.isArray(p.models?.[p.kind]) && p.models?.[p.kind]?.length ? p.models?.[p.kind]?.[0] : p.kind,
        createdAt: p.created_at || '',
      }));
  }, [data, queryClient, tenantId]);

  return (
    <>
      <Scroll>
        <Box p="$24" pb="$48">
          <Header size="x-large">
            <Header.Title title="LLMs" />
            <Header.Description>Manage Large Language Models available in this workspace.</Header.Description>
          </Header>

          <LLMsTable
            items={items}
            onCreate={() => router.navigate({ to: '/tenants/$tenantId/settings/llm/new', params: { tenantId } })}
            onEdit={(i) =>
              router.navigate({
                to: '/tenants/$tenantId/settings/llm/$platformId',
                params: { tenantId, platformId: i.id },
              })
            }
            onDelete={(i) => setDeleteTarget(i)}
          />
        </Box>
      </Scroll>
      {deleteTarget && (
        <Dialog open onClose={() => setDeleteTarget(null)}>
          <Dialog.Header>
            <Dialog.Header.Title title="Are you sure?" />
          </Dialog.Header>
          <Dialog.Content>
            Deleting an LLM will remove its configuration from this workspace. This cannot be undone.
          </Dialog.Content>
          <Dialog.Actions>
            <Button
              variant="primary"
              disabled={deleteMutation.isPending}
              onClick={() => deleteTarget && deleteMutation.mutateAsync({ tenantId, platformId: deleteTarget.id })}
            >
              Delete
            </Button>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
          </Dialog.Actions>
        </Dialog>
      )}
      <Outlet />
    </>
  );
}
