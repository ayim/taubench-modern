import { FC, useMemo } from 'react';
import { RouterProvider as RouterProviderBase, createRouter } from '@tanstack/react-router';

import { AgentAPIClient } from '~/lib/AgentAPIClient';
import { FullScreenLoader } from '~/components/Loaders';
import { routeTree } from '~/routeTree.gen';
import { queryClient } from './QueryClient';
import { useAuth } from '../ProtectedRoute';
import { ErrorRoute } from '../ErrorRoute';
import { NotFoundRoute } from '../NotFoundRoute';
import { SPARRouter } from '~/lib/trpc';
import { createTRPCQueryUtils } from '@trpc/react-query';
import { useUserPermissionsQuery } from '~/queries/userPermissions';
import { extractUserPermissions } from '~/lib/userPermissions';

export const router = createRouter({
  routeTree,
  defaultPendingComponent: FullScreenLoader,
  defaultPendingMs: 100,
  context: {
    trpc: undefined!,
    queryClient,
    agentAPIClient: undefined!,
    permissions: undefined!,
  },
  defaultErrorComponent: ErrorRoute,
  defaultNotFoundComponent: NotFoundRoute,
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

export const RouterProvider: FC<{ trpcUtils: ReturnType<typeof createTRPCQueryUtils<SPARRouter>> }> = ({
  trpcUtils,
}) => {
  const { getUserToken } = useAuth();
  const { data: userPermissions, isLoading: isLoadingUserPermissions } = useUserPermissionsQuery();

  const context = useMemo(() => {
    const agentAPIClient = new AgentAPIClient(getUserToken);

    return {
      queryClient,
      agentAPIClient,
      trpc: trpcUtils,
      permissions: extractUserPermissions(userPermissions),
    };
  }, [getUserToken, trpcUtils, userPermissions]);

  if (!context.agentAPIClient || isLoadingUserPermissions) {
    return <FullScreenLoader />;
  }

  return <RouterProviderBase router={router} context={context} />;
};
