import { Box, Button, Menu, Tooltip, Typography, useScreenSize } from '@sema4ai/components';
import { IconDotsHorizontal, IconLayoutRight, IconPaperclip, IconPieChart, IconPlus, IconPoll } from '@sema4ai/icons';
import { AgentIcon, useSidebarMenu } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { useMatchRoute, useParams } from '@tanstack/react-router';

import { useGetAgentQuery } from '~/queries/agents';

import { Header as HeaderBase } from '~/components/layout/Header';
import { RouterMenuLink, RouterSideNavigationLink } from '~/components/RouterLink';

const WorkItemsToggle = styled(Button)<{ $expanded?: boolean }>`
  display: ${({ $expanded }) => ($expanded ? 'none' : 'block')};
  position: relative;
  z-index: ${({ theme }) => theme.zIndex.dropdown + 1};
`;

export const Header = () => {
  const { agentId, tenantId } = useParams({ from: '/tenants/$tenantId/worker/$agentId' });
  const matchRoute = useMatchRoute();
  const { triggerProps, triggerRef } = useSidebarMenu('work-items-list');

  const { expanded: mainMenuExpanded } = useSidebarMenu('main-menu');
  const isMobile = useScreenSize('m');

  const { data: agent, isLoading } = useGetAgentQuery({ agentId, tenantId });

  const isDashboardView = matchRoute({ to: '/tenants/$tenantId/worker/$agentId/dashboard' });
  const workItemRouteParams = matchRoute({ to: '/tenants/$tenantId/worker/$agentId/$workItemId', fuzzy: true });

  const workItemId = (workItemRouteParams || {})?.workItemId;

  if (isLoading || !agent) {
    return null;
  }

  return (
    <HeaderBase $sidebarExpanded={mainMenuExpanded}>
      <WorkItemsToggle
        variant="ghost-subtle"
        icon={IconLayoutRight}
        aria-label="Toggle thread view"
        {...triggerProps}
        ref={triggerRef}
      />

      <Box display="flex" alignItems="center" gap="$12">
        <AgentIcon mode="worker" size="s" />
        <Typography variant="body-large" fontWeight="medium">
          {agent.name}
        </Typography>
      </Box>

      <Box display="flex" alignItems="center" gap="$8" ml="auto">
        <Tooltip text="New Work Item" placement="bottom">
          <RouterSideNavigationLink
            to="/tenants/$tenantId/worker/$agentId/create"
            params={{ tenantId, agentId }}
            icon={IconPlus}
            round
            aria-label="New Work Item"
          />
        </Tooltip>

        {!isMobile && (
          <>
            <Tooltip text="Work Items" placement="bottom">
              <RouterSideNavigationLink
                to="/tenants/$tenantId/worker/$agentId"
                icon={<IconPoll />}
                round
                params={{ tenantId, agentId }}
                activeOptions={{ exact: true }}
              />
            </Tooltip>

            {!isDashboardView && workItemId && (
              <Tooltip text="Files" placement="bottom">
                <RouterSideNavigationLink
                  to="/tenants/$tenantId/worker/$agentId/$workItemId/files"
                  icon={<IconPaperclip />}
                  round
                  params={{ tenantId, agentId, workItemId }}
                />
              </Tooltip>
            )}

            <Tooltip text="Dashboard" placement="bottom">
              <RouterSideNavigationLink
                to="/tenants/$tenantId/worker/$agentId/dashboard"
                icon={<IconPieChart />}
                round
                params={{ tenantId, agentId }}
                activeOptions={{ exact: true }}
              />
            </Tooltip>
          </>
        )}

        {isMobile && (
          <>
            <Menu trigger={<Button icon={IconDotsHorizontal} variant="ghost" aria-label="Chat Actions" />}>
              <RouterMenuLink
                to="/tenants/$tenantId/worker/$agentId/create"
                icon={IconPoll}
                params={{ tenantId, agentId }}
              >
                New Work Item
              </RouterMenuLink>
              <RouterMenuLink to="/tenants/$tenantId/worker/$agentId" icon={IconPoll} params={{ tenantId, agentId }}>
                Work Items
              </RouterMenuLink>

              {!isDashboardView && workItemId && (
                <RouterMenuLink
                  to="/tenants/$tenantId/worker/$agentId/$workItemId/files"
                  icon={IconPaperclip}
                  params={{ tenantId, agentId, workItemId }}
                >
                  Files
                </RouterMenuLink>
              )}

              <RouterMenuLink
                to="/tenants/$tenantId/worker/$agentId/dashboard"
                icon={IconPieChart}
                params={{ tenantId, agentId }}
              >
                Work Items
              </RouterMenuLink>
            </Menu>
          </>
        )}
      </Box>
    </HeaderBase>
  );
};
