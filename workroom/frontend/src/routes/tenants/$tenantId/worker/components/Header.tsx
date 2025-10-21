import { Button, Menu, Tooltip, useLocalStorage, useScreenSize } from '@sema4ai/components';
import { IconArrowLeft, IconDotsHorizontal, IconInformation, IconPaperclip, IconPoll } from '@sema4ai/icons';
import { WorkerHeader } from '@sema4ai/spar-ui';
import { useAgentQuery } from '@sema4ai/spar-ui/queries';
import { useNavigate, useParams } from '@tanstack/react-router';
import { useEffect, useState } from 'react';

import { RouterMenuLink, RouterSideNavigationLink } from '~/components/RouterLink';
import { useToggleRoutePath } from '~/hooks/useToggleRoutePath';
import { useTenantContext } from '~/lib/tenantContext';

type NavigationContext = {
  from: string;
  timestamp: number;
  tab: 'all' | 'overview';
  agent?: string;
  status?: string;
  search?: string;
  page?: string;
};

export const Header = () => {
  const { agentId, tenantId } = useParams({ from: '/tenants/$tenantId/worker/$agentId' });
  const { workItemId, threadId } = useParams({ strict: false });
  const navigate = useNavigate();

  const { features } = useTenantContext();
  const isMobile = useScreenSize('m');

  const { data: agent, isLoading } = useAgentQuery({ agentId });

  const { storageValue: storedContext, setStorageValue: setStoredContext } = useLocalStorage<NavigationContext | null>({
    key: `workItems.navigationContext${tenantId ? `.${tenantId}` : ''}`,
    defaultValue: null,
  });

  const [navigationContext, setNavigationContext] = useState<NavigationContext | null>(null);

  useEffect(() => {
    if (storedContext && storedContext.timestamp > Date.now() - 3600000) {
      setNavigationContext(storedContext);
    }
  }, [storedContext]);

  const handleBackToWorkItems = () => {
    const tab = navigationContext?.tab || 'all';
    const agent = navigationContext?.agent;
    const status = navigationContext?.status;
    const search = navigationContext?.search;
    const page = navigationContext?.page;

    setStoredContext(null);

    const searchParams: { tab: 'all' | 'overview'; agent?: string; status?: string; search?: string; page?: number } = {
      tab,
    };
    if (agent) searchParams.agent = agent;
    if (status) searchParams.status = status;
    if (search) searchParams.search = search;
    if (page) searchParams.page = Number(page);

    navigate({
      to: '/tenants/$tenantId/workItems',
      params: { tenantId },
      search: searchParams,
    });
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
        !isMobile && navigationContext?.from === 'workItems' ? (
          <Tooltip text="Back to Work Items" placement="bottom">
            <Button
              icon={IconArrowLeft}
              variant="ghost-subtle"
              round
              onClick={handleBackToWorkItems}
              aria-label="Back to Work Items"
            />
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
            <Menu.Item icon={IconArrowLeft} onClick={handleBackToWorkItems}>
              Back to Work Items
            </Menu.Item>

            {workItemId && threadId && (
              <>
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
