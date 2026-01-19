import { FC, useMemo } from 'react';
import { Box, Button, useScreenSize } from '@sema4ai/components';
import {
  IconAgents,
  IconSettings2,
  IconMcp,
  IconUsers,
  IconDatabase,
  IconPoll,
  IconLayoutLeft,
  IconMenu,
} from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { useMatch, useParams, useRouteContext } from '@tanstack/react-router';
import { SidebarMenu, useSidebarMenu } from '@sema4ai/layouts';
import { SIDEBAR_STARTING_WIDTH_PX } from '@sema4ai/spar-ui';

import { TenantMenu } from './components/TenantMenu';
import { RouterSideNavigationLink } from '~/components/RouterLink';

import { AgentsMenu } from './components/AgentsMenu';
import { UserMenu } from './components/UserMenu';
import { useTenantContext, shouldDisplayConfigurationSidebarLink } from '~/lib/tenantContext';
import { ADMINISTRATION_ACCESS_PERMISSION } from '~/lib/userPermissions';

type Props = {
  profilePictureUrl?: string;
};

const MenuOuterToggle = styled(Button)<{ $expanded?: boolean }>`
  display: block;
  position: absolute;
  top: ${({ theme }) => theme.space.$14};
  z-index: 1;

  ${({ theme }) => theme.screen.m} {
    display: block;
    top: ${({ theme }) => theme.space.$8};
    left: ${({ theme }) => theme.space.$8};
  }
`;

const ScrollContainer = styled.div`
  overflow: auto;
  padding: 0 ${({ theme }) => theme.space.$12};
  margin: 0 -${({ theme }) => theme.space.$12};
  flex: 1;
`;

const MenuToggle = () => {
  const { width, expanded, triggerProps, triggerRef } = useSidebarMenu('main-menu');
  const isMobile = useScreenSize('m');

  const isConversationalMatch = useMatch({ from: '/tenants/$tenantId/conversational/$agentId', shouldThrow: false });
  const isWorkerMatch = useMatch({ from: '/tenants/$tenantId/worker/$agentId', shouldThrow: false });

  /**
   * On these routes the header toggle is displayed in the chat header
   */
  const isChatHeaderToggle = isConversationalMatch || isWorkerMatch;

  const menuStyle = useMemo(() => {
    if (isMobile) {
      return { left: 8 };
    }

    if (!isChatHeaderToggle && !expanded) {
      return { left: 20 };
    }

    return { left: width - 48 };
  }, [width, isMobile, isChatHeaderToggle, expanded]);

  if ((isChatHeaderToggle && !expanded) || (isMobile && isChatHeaderToggle)) {
    return null;
  }

  return (
    <MenuOuterToggle
      ref={triggerRef}
      {...triggerProps}
      icon={expanded ? IconLayoutLeft : IconMenu}
      variant={expanded ? 'ghost-subtle' : 'ghost'}
      aria-label="Toggle main menu"
      style={menuStyle}
      $expanded={expanded}
      aria-expanded={false}
    />
  );
};

export const Sidebar: FC<Props> = ({ profilePictureUrl }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { features } = useTenantContext();
  const { permissions } = useRouteContext({ from: '/tenants/$tenantId' });

  return (
    <>
      <MenuToggle />

      <SidebarMenu
        name="main-menu"
        title="Main menu"
        initialWidth={SIDEBAR_STARTING_WIDTH_PX}
        minWidth={SIDEBAR_STARTING_WIDTH_PX}
        primary
      >
        <TenantMenu />
        <ScrollContainer>
          <Box as="nav">
            <RouterSideNavigationLink icon={<IconAgents />} to="/tenants/$tenantId/home" params={{ tenantId }}>
              Agents
            </RouterSideNavigationLink>

            {features.workerAgents.enabled && (
              <RouterSideNavigationLink
                icon={<IconPoll />}
                to="/tenants/$tenantId/workItems/overview"
                params={{ tenantId }}
              >
                Work Items
              </RouterSideNavigationLink>
            )}

            {permissions[ADMINISTRATION_ACCESS_PERMISSION] && features.deploymentWizard.enabled && (
              <RouterSideNavigationLink
                icon={<IconDatabase />}
                to="/tenants/$tenantId/data-access/data-connections"
                params={{ tenantId }}
              >
                Data
              </RouterSideNavigationLink>
            )}

            {permissions[ADMINISTRATION_ACCESS_PERMISSION] && features.mcpServersManagement.enabled && (
              <RouterSideNavigationLink icon={<IconMcp />} to="/tenants/$tenantId/mcp-servers" params={{ tenantId }}>
                MCP Servers
              </RouterSideNavigationLink>
            )}

            {permissions['users.read'] && features.userManagement.enabled && (
              <RouterSideNavigationLink icon={<IconUsers />} to="/tenants/$tenantId/users" params={{ tenantId }}>
                Users
              </RouterSideNavigationLink>
            )}

            {permissions[ADMINISTRATION_ACCESS_PERMISSION] && shouldDisplayConfigurationSidebarLink({ features }) && (
              <RouterSideNavigationLink
                icon={<IconSettings2 />}
                to="/tenants/$tenantId/configuration"
                params={{ tenantId }}
              >
                Configuration
              </RouterSideNavigationLink>
            )}
          </Box>

          <AgentsMenu />
        </ScrollContainer>

        <Box display="flex" mt="auto" pr="$8">
          <UserMenu profilePictureUrl={profilePictureUrl} />
        </Box>
      </SidebarMenu>
    </>
  );
};
