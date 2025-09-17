import { FC, useMemo } from 'react';
import { Box, Button, Link } from '@sema4ai/components';
import {
  IconAgents,
  IconArrowUpRight,
  IconFileText,
  IconHelpCircle,
  IconMenu,
  IconSettings2,
  IconMcp,
} from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { useParams } from '@tanstack/react-router';
import { SidebarMenu, useSidebarMenu } from '@sema4ai/layouts';

import { EXTERNAL_LINKS } from '~/config/externalLinks';
import { TenantMenu } from './components/TenantMenu';
import { RouterSideNavigationLink } from '~/components/RouterLink';

import { AgentsMenu } from './components/AgentsMenu';
import { UserMenu } from './components/UserMenu';
import { useTenantContext } from '~/lib/tenantContext';

const MenuOuterToggle = styled(Button)<{ $expanded?: boolean }>`
  display: block;
  position: absolute;
  top: ${({ theme }) => theme.space.$14};
  z-index: ${({ theme }) => theme.zIndex.dropdown + 1};

  ${({ theme }) => theme.screen.m} {
    display: block;
    top: ${({ theme }) => theme.space.$8};
    left: ${({ theme }) => theme.space.$8};
  }
`;

export const Sidebar: FC = () => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { features } = useTenantContext();
  const { triggerProps, triggerRef } = useSidebarMenu('main-menu');
  const { width, expanded } = useSidebarMenu('main-menu');

  const menuStyle = useMemo(() => {
    return {
      left: expanded ? width - 48 : 20,
    };
  }, [width, expanded]);

  return (
    <>
      <MenuOuterToggle
        ref={triggerRef}
        {...triggerProps}
        icon={IconMenu}
        variant="ghost-subtle"
        aria-label="Toggle main menu"
        style={menuStyle}
      />

      <SidebarMenu name="main-menu" title="Main menu" minWidth={240} primary>
        <TenantMenu />

        <Box as="nav">
          <RouterSideNavigationLink icon={<IconAgents />} to="/tenants/$tenantId/home" params={{ tenantId }}>
            Agents
          </RouterSideNavigationLink>

          {/* {features.documentIntelligence.enabled && ( */}
          {/* <RouterSideNavigationLink
              icon={<IconFileText />}
              to="/tenants/$tenantId/documentIntelligence"
              params={{ tenantId }}
            >
              Documents
            </RouterSideNavigationLink> */}
          {/* )} */}

          {features.deploymentWizard.enabled && (
            <RouterSideNavigationLink icon={<IconAgents />} to="/tenants/$tenantId/agents/deploy" params={{ tenantId }}>
              Deploy Agent
            </RouterSideNavigationLink>
          )}

          {features.mcpServersManagement.enabled && (
            <RouterSideNavigationLink icon={<IconMcp />} to="/tenants/$tenantId/mcp-servers" params={{ tenantId }}>
              MCP Servers
            </RouterSideNavigationLink>
          )}

          {false && features.agentEvals.enabled && (
            <RouterSideNavigationLink icon={<IconSettings2 />} to="/tenants/$tenantId/agentEvals" params={{ tenantId }}>
              Evals
            </RouterSideNavigationLink>
          )}

          <RouterSideNavigationLink icon={<IconFileText />} to="/tenants/$tenantId/workItems" params={{ tenantId }}>
            Work Items
          </RouterSideNavigationLink>

          <RouterSideNavigationLink
            icon={<IconSettings2 />}
            to="/tenants/$tenantId/configuration"
            params={{ tenantId }}
          >
            Configuration
          </RouterSideNavigationLink>
        </Box>

        <AgentsMenu />

        <Box display="flex" justifyContent="space-between" mt="auto">
          <UserMenu />

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
