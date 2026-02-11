import { Outlet, createRootRouteWithContext } from '@tanstack/react-router';
import { QueryClient } from '@tanstack/react-query';
import type { CreateQueryUtils } from '@trpc/react-query/shared';

import { AgentAPIClient } from '~/lib/AgentAPIClient';
import { SPARRouter } from '~/lib/trpc';
import type { UserPermission } from '~/lib/userPermissions';

interface RouterContext {
  queryClient: QueryClient;
  agentAPIClient: AgentAPIClient;
  trpc: CreateQueryUtils<SPARRouter>;
  permissions: Record<UserPermission, boolean>;
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: View,
});

function View() {
  return <Outlet />;
}
