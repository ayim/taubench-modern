import { Button, Menu, Tooltip, useScreenSize } from '@sema4ai/components';
import {
  IconArrowLeft,
  IconDataframe,
  IconDotsHorizontal,
  IconInformation,
  IconPaperclip,
  IconPoll,
} from '@sema4ai/icons';
import { WorkerHeader } from '~/components/WorkerHeader';
import { useAgentQuery } from '~/queries/agents';
import { useParams, useRouter, useSearch } from '@tanstack/react-router';

import { RouterMenuLink, RouterSideNavigationLink } from '~/components/RouterLink';
import { useToggleRoutePath } from '~/hooks/useToggleRoutePath';
import { useTenantContext } from '~/lib/tenantContext';

export const Header = () => {
  const { agentId, tenantId } = useParams({ from: '/tenants/$tenantId/worker/$agentId' });
  const { workItemId, threadId } = useParams({ strict: false });
  const router = useRouter();
  const searchParams = useSearch({ strict: false });

  const { features } = useTenantContext();
  const isMobile = useScreenSize('m');

  const { data: agent, isLoading } = useAgentQuery({ agentId });

  const isUserComingFromWorkItemsListView = searchParams.from === 'workItemsListView';

  const handleBack = () => {
    router.history.back();
  };

  const defaultLink = {
    to: '/tenants/$tenantId/worker/$agentId/$workItemId/$threadId',
    params: { tenantId, agentId, workItemId, threadId },
  };

  const resolveLink = useToggleRoutePath(defaultLink);

  if (isLoading || !agent) {
    return null;
  }

  return (
    <WorkerHeader
      leftAction={
        !isMobile && isUserComingFromWorkItemsListView ? (
          <Tooltip text="Back" placement="bottom">
            <Button icon={IconArrowLeft} variant="ghost-subtle" round onClick={handleBack} aria-label="Back" />
          </Tooltip>
        ) : undefined
      }
    >
      {!isMobile && (
        <>
          {workItemId && threadId && (
            <>
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

              <Tooltip text="Data Frames" placement="bottom">
                <RouterSideNavigationLink
                  icon={<IconDataframe />}
                  round
                  {...resolveLink('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/data-frames', {
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

              {features.agentDetails.enabled && (
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
              )}
            </>
          )}
        </>
      )}

      {isMobile && (
        <>
          <Menu trigger={<Button icon={IconDotsHorizontal} variant="ghost" aria-label="Chat Actions" />}>
            {isUserComingFromWorkItemsListView && (
              <Menu.Item icon={IconArrowLeft} onClick={handleBack}>
                Back
              </Menu.Item>
            )}

            {workItemId && threadId && (
              <>
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
                  icon={IconDataframe}
                  {...resolveLink('/tenants/$tenantId/worker/$agentId/$workItemId/$threadId/data-frames', {
                    tenantId,
                    agentId,
                    workItemId,
                    threadId,
                  })}
                >
                  Data Frames
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
                {features.agentDetails.enabled && (
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
                )}
              </>
            )}
          </Menu>
        </>
      )}
    </WorkerHeader>
  );
};
