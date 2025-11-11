import { FC, useMemo } from 'react';
import { Box, Button, Link, useScreenSize } from '@sema4ai/components';
import {
  IconAgents,
  IconArrowUpRight,
  IconFileText,
  IconHelpCircle,
  IconMenu,
  IconSettings2,
  IconMcp,
  IconUsers,
} from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { useParams, useRouteContext } from '@tanstack/react-router';
import { SidebarMenu, useSidebarMenu } from '@sema4ai/layouts';
import { SIDEBAR_STARTING_WIDTH_PX } from '@sema4ai/spar-ui';

import { EXTERNAL_LINKS } from '~/config/externalLinks';
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

export const Sidebar: FC<Props> = ({ profilePictureUrl }) => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { features } = useTenantContext();
  const { permissions } = useRouteContext({ from: '/tenants/$tenantId' });
  const { width, expanded, triggerProps, triggerRef } = useSidebarMenu('main-menu');
  const isMobile = useScreenSize('m');

  const menuStyle = useMemo(() => {
    if (isMobile) {
      return {
        left: 8,
      };
    }
    return {
      left: expanded ? width - 48 : 20,
    };
  }, [width, expanded, isMobile]);

  return (
    <>
      <MenuOuterToggle
        ref={triggerRef}
        {...triggerProps}
        icon={IconMenu}
        variant="ghost-subtle"
        aria-label="Toggle main menu"
        style={menuStyle}
        $expanded={expanded}
      />

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

            {permissions[ADMINISTRATION_ACCESS_PERMISSION] && features.deploymentWizard.enabled && (
              <RouterSideNavigationLink
                icon={<IconAgents />}
                to="/tenants/$tenantId/data-access/data-connections"
                params={{ tenantId }}
              >
                Data Access
              </RouterSideNavigationLink>
            )}

            {permissions[ADMINISTRATION_ACCESS_PERMISSION] && features.mcpServersManagement.enabled && (
              <RouterSideNavigationLink icon={<IconMcp />} to="/tenants/$tenantId/mcp-servers" params={{ tenantId }}>
                MCP Servers
              </RouterSideNavigationLink>
            )}

            {features.workerAgents.enabled && (
              <RouterSideNavigationLink
                icon={<IconFileText />}
                to="/tenants/$tenantId/workItems/overview"
                params={{ tenantId }}
              >
                Work Items
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

            {permissions['users.read'] && (
              <RouterSideNavigationLink icon={<IconUsers />} to="/tenants/$tenantId/users" params={{ tenantId }}>
                Users
              </RouterSideNavigationLink>
            )}
          </Box>

          <AgentsMenu />
        </ScrollContainer>

        <Box display="flex" justifyContent="space-between" mt="auto">
          <UserMenu profilePictureUrl={profilePictureUrl} />

          <Link
            href={EXTERNAL_LINKS.MAIN_WORKROOM_HELP}
            variant="subtle"
            icon={IconHelpCircle}
            iconAfter={IconArrowUpRight}
            target="_blank"
          >
            Help
          </Link>
        </Box>
      </SidebarMenu>
    </>
  );
};
