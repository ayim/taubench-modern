import { useMemo } from 'react';
import { RouterProvider as RouterProviderBase, createRouter } from '@tanstack/react-router';

import { AgentAPIClient } from '~/lib/AgentAPIClient';
import { InlineLoader } from '~/components/Loaders';
import { routeTree } from '~/routeTree.gen';
import { queryClient } from './QueryClient';
import { useAuth } from '../ProtectedRoute';
import { ErrorRoute } from '../ErrorRoute';
import { NotFoundRoute } from '../NotFoundRoute';

export const router = createRouter({
  routeTree,
  defaultPendingComponent: InlineLoader,
  defaultPendingMs: 100,
  context: {
    queryClient,
    agentAPIClient: undefined!,
  },
  defaultErrorComponent: ErrorRoute,
  defaultNotFoundComponent: NotFoundRoute,
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

export const RouterProvider = () => {
  const { getUserToken } = useAuth();

  const context = useMemo(() => {
    const agentAPIClient = new AgentAPIClient(getUserToken);

    return {
      queryClient,
      agentAPIClient,
    };
  }, [getUserToken]);

  if (!context.agentAPIClient) {
    return <InlineLoader />;
  }

  return <RouterProviderBase router={router} context={context} />;
};
