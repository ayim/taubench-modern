import { createFileRoute, redirect, Outlet } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { Box } from '@sema4ai/components';
import { Page } from '~/components/layout/Page';
import { trpc } from '~/lib/trpc';
import { UsersTable } from './users/components/UsersTable';

export const Route = createFileRoute('/tenants/$tenantId/users')({
  beforeLoad: async ({ context: { permissions }, params: { tenantId } }) => {
    if (!permissions['users.read']) {
      throw redirect({ to: '/tenants/$tenantId/home', params: { tenantId } });
    }
  },
  loader: async ({ context: { trpc } }) => {
    const users = await trpc.userManagement.listUsers.ensureData();
    return { users };
  },
  component: RouteComponent,
});

function RouteComponent() {
  const trpcUtils = trpc.useUtils();
  const initialData = Route.useLoaderData();
  const { tenantId } = Route.useParams();
  const { permissions } = Route.useRouteContext();
  const canUpdateUsers = permissions['users.write'];

  const { data: userList } = useQuery({
    ...trpcUtils.userManagement.listUsers.queryOptions(),
    initialData: initialData.users,
  });

  return (
    <Page title="Users">
      <Box mt="$8">
        <UsersTable items={userList.users} tenantId={tenantId} canUpdateUsers={canUpdateUsers} />
      </Box>
      <Outlet />
    </Page>
  );
}
