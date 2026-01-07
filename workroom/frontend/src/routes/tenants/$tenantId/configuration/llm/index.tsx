import { Outlet, createFileRoute, useNavigate, useRouteContext } from '@tanstack/react-router';
import { useMemo, useState } from 'react';
import { useQueryClient, useSuspenseQuery } from '@tanstack/react-query';
import { Dialog, Button, useSnackbar } from '@sema4ai/components';
import { LLMsTable, LLMTableItem } from '~/components/platforms/llms/components/LLMsTable';
import { getListPlatformsQueryOptions, type ListPlatformsResponse, useDeleteLLMMutation } from '~/queries/platforms';
import { getAlowedModelFromPlatform } from '~/lib/utils';

export const Route = createFileRoute('/tenants/$tenantId/configuration/llm/')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { tenantId } }) => {
    await queryClient.ensureQueryData(getListPlatformsQueryOptions({ agentAPIClient, tenantId }));
    return {};
  },
  component: RouteComponent,
});

function RouteComponent() {
  const { tenantId } = Route.useParams();
  useRouteContext({ from: '/tenants/$tenantId' });
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<LLMTableItem | null>(null);
  const { addSnackbar } = useSnackbar();

  const deleteMutation = useDeleteLLMMutation();

  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const { data } = useSuspenseQuery(getListPlatformsQueryOptions({ agentAPIClient, tenantId }));

  const handleDelete = () => {
    if (deleteTarget) {
      deleteMutation.mutate(
        { tenantId, platformId: deleteTarget.id },
        {
          onSuccess: () => {
            addSnackbar({
              message: 'LLM deleted successfully',
              variant: 'success',
            });
            setDeleteTarget(null);
          },
          onError: (e) => {
            addSnackbar({
              message: e instanceof Error ? e.message : 'Failed to delete LLM',
              variant: 'danger',
            });
          },
        },
      );
    }
  };

  const items = useMemo<LLMTableItem[]>(() => {
    const platforms: ListPlatformsResponse | undefined = data ?? queryClient.getQueryData(['platforms', tenantId]);
    return (platforms || [])
      .filter((p) => Boolean(p.platform_id))
      .map((p) => ({
        id: p.platform_id as string,
        name: p.name,
        platform: p.kind,
        model: getAlowedModelFromPlatform(p),
        createdAt: p.created_at || '',
      }));
  }, [data, queryClient, tenantId]);

  return (
    <>
      <LLMsTable
        items={items}
        onCreate={() => navigate({ to: '/tenants/$tenantId/configuration/llm/new', params: { tenantId } })}
        onEdit={(i) =>
          navigate({
            to: '/tenants/$tenantId/configuration/llm/$platformId',
            params: { tenantId, platformId: i.id },
          })
        }
        onDelete={(i) => setDeleteTarget(i)}
      />
      {deleteTarget && (
        <Dialog open onClose={() => setDeleteTarget(null)}>
          <Dialog.Header>
            <Dialog.Header.Title title="Are you sure?" />
          </Dialog.Header>
          <Dialog.Content>
            Deleting an LLM will remove its configuration from this workspace. This cannot be undone.
          </Dialog.Content>
          <Dialog.Actions>
            <Button variant="destructive" disabled={deleteMutation.isPending} onClick={handleDelete}>
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
