import { useMatchRoute, useNavigate, useParams } from '@tanstack/react-router';
import { styled } from '@sema4ai/theme';
import { AgentIcon, useSidebarMenu } from '@sema4ai/layouts';
import { Box, Button, Menu, SideNavigation, Tooltip, Typography, useScreenSize } from '@sema4ai/components';
import { ThreadSearch } from '@sema4ai/spar-ui';

import { useGetAgentQuery } from '~/queries/agents';
import {
  IconDotsHorizontal,
  IconDoubleChatBubble,
  IconLayoutRight,
  IconPaperclip,
  IconSpreadsheet,
  IconWriteNote,
} from '@sema4ai/icons';

import { Header as HeaderBase } from '~/components/layout/Header';
import { RouterMenuLink, RouterSideNavigationLink } from '~/components/RouterLink';
import { useCreateThreadMutation, useThreadsQuery } from '~/queries/threads';
import { NEW_CHAT_STARTING_MSG } from '~/config/constants';

const ThreadsToggle = styled(Button)<{ $expanded?: boolean }>`
  display: ${({ $expanded }) => ($expanded ? 'none' : 'block')};
  position: relative;
  z-index: ${({ theme }) => theme.zIndex.dropdown + 1};
`;

export const Header = () => {
  const { agentId, tenantId, threadId } = useParams({ from: '/tenants/$tenantId/conversational/$agentId/$threadId' });
  const matchRoute = useMatchRoute();
  const { triggerProps, triggerRef } = useSidebarMenu('threads-list');
  const { expanded: mainMenuExpanded } = useSidebarMenu('main-menu');
  const navigate = useNavigate();

  const { mutate: createThread, isPending: isCreatingThread } = useCreateThreadMutation({ agentId, tenantId });
  const { data: threads } = useThreadsQuery({ agentId, tenantId });
  const isMobile = useScreenSize('m');

  const { data: agent, isLoading } = useGetAgentQuery({ agentId, tenantId });

  const onNewThread = async () => {
    const name = threads ? `Chat ${threads?.length + 1}` : 'New chat';
    createThread(
      { name, startingMessage: NEW_CHAT_STARTING_MSG },
      {
        onSuccess: (data) => {
          if (!data.success) {
            return;
          }

          if (!data.data.thread_id) {
            // TODO-V2: Why can thread_id be null?
            return;
          }

          navigate({
            to: '/tenants/$tenantId/conversational/$agentId/$threadId',
            params: { threadId: data.data.thread_id, agentId, tenantId },
          });
        },
      },
    );
  };

  const isChatView = matchRoute({ to: '/tenants/$tenantId/conversational/$agentId/$threadId' });

  if (isLoading || !agent) {
    return null;
  }

  return (
    <HeaderBase $sidebarExpanded={mainMenuExpanded}>
      {isChatView && (
        <ThreadsToggle
          variant="ghost-subtle"
          icon={IconLayoutRight}
          aria-label="Toggle thread view"
          {...triggerProps}
          ref={triggerRef}
        />
      )}
      <Box display="flex" alignItems="center" gap="$12">
        <AgentIcon mode="conversational" size="s" />
        <Typography variant="body-large" fontWeight="medium">
          {agent.name}
        </Typography>
      </Box>
      <Box display="flex" alignItems="center" gap="$8" ml="auto">
        <Tooltip text="New Thread" placement="bottom">
          <SideNavigation.Item
            icon={IconWriteNote}
            disabled={isCreatingThread}
            round
            aria-label="New Thread"
            onClick={onNewThread}
          />
        </Tooltip>
        {!isMobile && (
          <>
            <Tooltip text="Chat" placement="bottom">
              <RouterSideNavigationLink
                to="/tenants/$tenantId/conversational/$agentId/$threadId"
                icon={<IconDoubleChatBubble />}
                round
                params={{ tenantId, agentId, threadId }}
                activeOptions={{ exact: true }}
              />
            </Tooltip>

            <Tooltip text="Files" placement="bottom">
              <RouterSideNavigationLink
                to="/tenants/$tenantId/conversational/$agentId/$threadId/files"
                icon={<IconPaperclip />}
                round
                params={{ tenantId, agentId, threadId }}
              />
            </Tooltip>

            <Tooltip text="Data Frames" placement="bottom">
              <RouterSideNavigationLink
                to="/tenants/$tenantId/conversational/$agentId/$threadId/data-frames"
                icon={<IconSpreadsheet />}
                round
                params={{ tenantId, agentId, threadId }}
              />
            </Tooltip>
          </>
        )}
        {isMobile && (
          <>
            <Menu trigger={<Button icon={IconDotsHorizontal} variant="ghost" aria-label="Chat Actions" />}>
              <RouterMenuLink
                to="/tenants/$tenantId/conversational/$agentId/$threadId"
                icon={IconDoubleChatBubble}
                params={{ tenantId, agentId, threadId }}
              >
                Chat
              </RouterMenuLink>
              <RouterMenuLink
                to="/tenants/$tenantId/conversational/$agentId/$threadId/files"
                icon={IconPaperclip}
                params={{ tenantId, agentId, threadId }}
              >
                Files
              </RouterMenuLink>
              <RouterMenuLink
                to="/tenants/$tenantId/conversational/$agentId/$threadId/data-frames"
                icon={IconSpreadsheet}
                params={{ tenantId, agentId, threadId }}
              >
                Data Frames
              </RouterMenuLink>
            </Menu>
          </>
        )}
        <ThreadSearch />
      </Box>
    </HeaderBase>
  );
};
