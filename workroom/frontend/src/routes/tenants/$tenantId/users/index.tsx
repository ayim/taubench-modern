import { Box } from '@sema4ai/components';
import { useQuery } from '@tanstack/react-query';
import { createFileRoute, redirect } from '@tanstack/react-router';
import { Page } from '~/components/layout/Page';
import { trpc } from '~/lib/trpc';
import { UsersTable } from './components/UsersTable';

export const Route = createFileRoute('/tenants/$tenantId/users/')({
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

  const { data: userList } = useQuery({
    ...trpcUtils.userManagement.listUsers.queryOptions(),
    initialData: initialData.users,
  });

  return (
    <Page title="Sema4.ai Users">
      <Box mt="$8">
        <UsersTable items={userList.users} />
      </Box>
    </Page>
  );
}
