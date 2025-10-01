import { Button, Menu, Tooltip, useScreenSize } from '@sema4ai/components';
import { IconDotsHorizontal, IconInformation, IconPaperclip, IconPlus, IconPoll } from '@sema4ai/icons';
import { WorkerHeader } from '@sema4ai/spar-ui';
import { useAgentQuery } from '@sema4ai/spar-ui/queries';
import { useParams } from '@tanstack/react-router';

import { RouterMenuLink, RouterSideNavigationLink } from '~/components/RouterLink';
import { useToggleRoutePath } from '~/hooks/useToggleRoutePath';

export const Header = () => {
  const { agentId, tenantId } = useParams({ from: '/tenants/$tenantId/worker/$agentId' });
  const { workItemId, threadId } = useParams({ strict: false });

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
    <WorkerHeader>
      {!isMobile && (
        <>
          {workItemId && threadId && (
            <>
              <Tooltip text="Details" placement="bottom">
                <RouterSideNavigationLink
                  icon={<IconInformation />}
                  round
                  {...resolveLink('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/chat-details', {
                    tenantId,
                    agentId,
                    workItemId,
                    threadId,
                  })}
                />
              </Tooltip>
              <Tooltip text="Work Item Details" placement="bottom">
                <RouterSideNavigationLink
                  icon={<IconPoll />}
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
                  {...resolveLink('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/chat-details', {
                    tenantId,
                    agentId,
                    workItemId,
                    threadId,
                  })}
                >
                  Details
                </RouterMenuLink>
                <RouterMenuLink
                  icon={IconPoll}
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
    </WorkerHeader>
  );
};
