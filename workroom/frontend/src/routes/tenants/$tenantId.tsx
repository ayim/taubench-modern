import { useMemo } from 'react';
import { SparUIContext } from '~/api/context';
import { Outlet, createFileRoute, useRouteContext } from '@tanstack/react-router';
import { SidebarMenuProvider } from '@sema4ai/layouts';
import { Box, Button, EmptyState } from '@sema4ai/components';

import errorIllustration from '~/assets/error.svg';
import { TenantContext } from '~/lib/tenantContext';
import { getMeta } from '~/lib/meta';
import { trpc } from '~/lib/trpc';
import { Main } from './components/Main';
import { Sidebar } from './components/sidebar';

export const Route = createFileRoute('/tenants/$tenantId')({
  loader: async ({ context: { agentAPIClient } }) => {
    const tenantMeta = await agentAPIClient.getTenantMeta();
    const applicationMeta = await getMeta();

    return {
      tenantMeta: tenantMeta
        ? {
            ...tenantMeta,
            branding: applicationMeta.branding,
          }
        : undefined,
    };
  },
  component: View,
});

function View() {
  const { tenantId } = Route.useParams();
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const { tenantMeta } = Route.useLoaderData();

  const profileData = trpc.profile.getProfile.useQuery();
  const profilePicture = (profileData.isSuccess && profileData.data.user.profilePicture) || undefined;

  const extConfigStatus = trpc.externalConfiguration.getExternalConfigurationStatus.useQuery();
  const snowflakeEAIUrl = extConfigStatus.isSuccess ? extConfigStatus.data.snowflakeEAIUrl : null;

  const sparUIContext = useMemo(() => {
    return {
      agentAPIClient,
      tenantId,
      platformConfig: {
        snowflakeEAIUrl,
      },
    };
  }, [agentAPIClient, tenantId, snowflakeEAIUrl]);

  if (!tenantMeta || !sparUIContext) {
    return (
      <Box display="flex" justifyContent="center" flexDirection="column" maxHeight={960} height="calc(100% - 72px)">
        <EmptyState
          illustration={<img src={errorIllustration} loading="lazy" alt="" />}
          title="Internal error"
          description="Workspace data could not be loaded."
          action={
            <Button onClick={() => window.location.reload()} round>
              Reload page
            </Button>
          }
        />
      </Box>
    );
  }

  return (
    <TenantContext.Provider value={tenantMeta}>
      <SparUIContext.Provider value={sparUIContext}>
        <Main>
          <SidebarMenuProvider>
            <Sidebar profilePictureUrl={profilePicture} />
            <Outlet />
          </SidebarMenuProvider>
        </Main>
      </SparUIContext.Provider>
    </TenantContext.Provider>
  );
}
