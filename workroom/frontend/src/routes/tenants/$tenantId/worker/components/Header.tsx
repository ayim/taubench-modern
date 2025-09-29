import { Box, Button, Menu, Tooltip, Typography, useScreenSize } from '@sema4ai/components';
import { IconDotsHorizontal, IconInformation, IconLayoutRight, IconPaperclip, IconPlus } from '@sema4ai/icons';
import { AgentIcon, useSidebarMenu } from '@sema4ai/layouts';
import { useAgentQuery } from '@sema4ai/spar-ui/queries';
import { styled } from '@sema4ai/theme';
import { useParams } from '@tanstack/react-router';

import { Header as HeaderBase } from '~/components/layout/Header';
import { RouterMenuLink, RouterSideNavigationLink } from '~/components/RouterLink';
import { useToggleRoutePath } from '~/hooks/useToggleRoutePath';

const WorkItemsToggle = styled(Button)<{ $expanded?: boolean }>`
  display: ${({ $expanded }) => ($expanded ? 'none' : 'block')};
  position: relative;
  z-index: ${({ theme }) => theme.zIndex.dropdown + 1};
`;

export const Header = () => {
  const { agentId, tenantId } = useParams({ from: '/tenants/$tenantId/worker/$agentId' });
  const { workItemId, threadId } = useParams({ strict: false });

  const { triggerProps, triggerRef } = useSidebarMenu('work-items-list');
  const { expanded: mainMenuExpanded } = useSidebarMenu('main-menu');
  const isMobile = useScreenSize('m');

  const { data: agent, isLoading } = useAgentQuery({ agentId });

  const defaultLink = {
    to: '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId',
    params: { tenantId, agentId, workItemId, threadId },
  };

  const resolveLink = useToggleRoutePath(defaultLink);

  if (isLoading || !agent) {
    return null;
  }

  return (
    <HeaderBase $sidebarExpanded={mainMenuExpanded}>
      <WorkItemsToggle
        variant="ghost-subtle"
        icon={IconLayoutRight}
        aria-label="Toggle work item view"
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
            {workItemId && threadId && (
              <>
                <Tooltip text="Work Item Details" placement="bottom">
                  <RouterSideNavigationLink
                    icon={<IconInformation />}
                    round
                    {...resolveLink('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/workitem-details', {
                      tenantId,
                      agentId,
                      workItemId,
                      threadId,
                    })}
                  />
                </Tooltip>

                <Tooltip text="Files" placement="bottom">
                  <RouterSideNavigationLink
                    icon={<IconPaperclip />}
                    round
                    {...resolveLink('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/files', {
                      tenantId,
                      agentId,
                      workItemId,
                      threadId,
                    })}
                  />
                </Tooltip>
              </>
            )}
          </>
        )}

        {isMobile && (
          <>
            <Menu trigger={<Button icon={IconDotsHorizontal} variant="ghost" aria-label="Chat Actions" />}>
              <RouterMenuLink
                to="/tenants/$tenantId/worker/$agentId/create"
                icon={IconPlus}
                params={{ tenantId, agentId }}
              >
                New Work Item
              </RouterMenuLink>

              {workItemId && threadId && (
                <>
                  <RouterMenuLink
                    icon={IconInformation}
                    {...resolveLink('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/workitem-details', {
                      tenantId,
                      agentId,
                      workItemId,
                      threadId,
                    })}
                  >
                    Work Item Details
                  </RouterMenuLink>
                  <RouterMenuLink
                    icon={IconPaperclip}
                    {...resolveLink('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/files', {
                      tenantId,
                      agentId,
                      workItemId,
                      threadId,
                    })}
                  >
                    Files
                  </RouterMenuLink>
                </>
              )}
            </Menu>
          </>
        )}
      </Box>
    </HeaderBase>
  );
};
