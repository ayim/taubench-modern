import { createFileRoute, redirect } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { trpc } from '~/lib/trpc';
import { UserRoleDialog } from './components/UserRoleDialog';

export const Route = createFileRoute('/tenants/$tenantId/users/$userId/update')({
  beforeLoad: async ({ context: { permissions }, params: { tenantId } }) => {
    if (!permissions['users.write']) {
      throw redirect({ to: '/tenants/$tenantId/users', params: { tenantId } });
    }
  },
  loader: async ({ context: { trpc }, params: { userId } }) => {
    const user = await trpc.userManagement.getUserDetails.ensureData({ userId });
    const roles = await trpc.userManagement.listAvailableRoles.ensureData();
    return { user, roles };
  },
  component: RouteComponent,
});

function RouteComponent() {
  const initialData = Route.useLoaderData();
  const { tenantId, userId } = Route.useParams();
  const navigate = Route.useNavigate();

  const trpcUtils = trpc.useUtils();

  const { data: user } = useQuery({
    ...trpcUtils.userManagement.getUserDetails.queryOptions({ userId }),
    initialData: initialData.user,
  });

  const { data: rolesResult } = useQuery({
    ...trpcUtils.userManagement.listAvailableRoles.queryOptions(),
    initialData: initialData.roles,
  });

  return (
    <UserRoleDialog
      user={user}
      roles={rolesResult.roles}
      onClose={() => navigate({ to: '/tenants/$tenantId/users', params: { tenantId } })}
      open
    />
  );
}
