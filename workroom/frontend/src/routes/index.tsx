import { createFileRoute, redirect } from '@tanstack/react-router';
import { Box, Button, EmptyState } from '@sema4ai/components';
import { useAuth } from '@sema4ai/robocloud-ui-utils';

import { listUserTenantsQueryOptions } from '~/queries/tenants';
import errorIllustration from '~/assets/error.svg';
import { z } from 'zod';

const globalSearchParams = z.object({
  from: z.enum(['workItemsListView']).optional(),
});

export const Route = createFileRoute('/')({
  validateSearch: (search: Record<string, unknown>) => {
    return globalSearchParams.parse(search);
  },
  component: View,
  loader: async ({ context: { agentAPIClient, queryClient } }) => {
    const tenants = await queryClient.ensureQueryData(
      listUserTenantsQueryOptions({
        agentAPIClient,
      }),
    );

    if (tenants?.length) {
      throw redirect({ to: '/tenants/$tenantId/home', params: { tenantId: tenants[0].id } });
    }

    return tenants;
  },
});

function View() {
  const { logout } = useAuth();

  return (
    <Box display="flex" justifyContent="center" flexDirection="column" maxHeight={960} height="calc(100% - 72px)">
      <EmptyState
        illustration={<img src={errorIllustration} loading="lazy" alt="" />}
        title="No Workspace found"
        description="There are no Agent enabled Workspaces available for you yet"
        action={
          <Button onClick={() => logout({ returnTo: `${window.location.origin}/signout-callback` })} round>
            Log out
          </Button>
        }
      />
    </Box>
  );
}
