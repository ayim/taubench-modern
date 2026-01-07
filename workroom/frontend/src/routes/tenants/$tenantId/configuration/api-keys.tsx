import { Outlet, createFileRoute } from '@tanstack/react-router';
import { ApiKeysTable, type ApiKeyTableItem } from '~/components/apiKeys/ApiKeysTable';
import { trpc } from '~/lib/trpc';

export const Route = createFileRoute('/tenants/$tenantId/configuration/api-keys')({
  component: RouteComponent,
  loader: async ({ context: { trpc } }) => {
    const apiKeysData = await trpc.apiKeys.list.ensureData();
    return { apiKeysData };
  },
});

function RouteComponent() {
  const { tenantId } = Route.useParams();
  const { apiKeysData: initialApiKeysData } = Route.useLoaderData();

  const { data: apiKeysData } = trpc.apiKeys.list.useQuery(undefined, { initialData: initialApiKeysData });

  const items: ApiKeyTableItem[] = apiKeysData.apiKeys.map((apiKey) => ({
    id: apiKey.id,
    name: apiKey.name,
    createdAt: apiKey.createdAt,
    lastUsedAt: apiKey.lastUsedAt,
  }));

  return (
    <>
      <ApiKeysTable items={items} tenantId={tenantId} />
      <Outlet />
    </>
  );
}
