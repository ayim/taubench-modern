import { lazy } from 'react';
import { Outlet, createRootRouteWithContext } from '@tanstack/react-router';
import { QueryClient } from '@tanstack/react-query';

import { AgentAPIClient } from '~/lib/AgentAPIClient';

interface RouterContext {
  queryClient: QueryClient;
  agentAPIClient: AgentAPIClient;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: View,
});

const TanStackRouterDevtools =
  process.env.NODE_ENV !== 'development'
    ? () => null
    : lazy(() =>
        import('@tanstack/router-devtools').then((res) => ({
          default: res.TanStackRouterDevtools,
        })),
      );

function View() {
  return (
    <>
      <Outlet />
      <TanStackRouterDevtools position="bottom-right" />
    </>
  );
}
