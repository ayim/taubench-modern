import { FC, ReactNode } from 'react';
import { styled } from '@sema4ai/theme';
import { AgentIcon, useSidebarMenu } from '@sema4ai/layouts';
import { Box, Button, SideNavigation, Tooltip, Typography, useSnackbar } from '@sema4ai/components';
import { IconLayoutRight, IconWriteNote } from '@sema4ai/icons';

import { useNavigate, useParams } from '../../hooks';
import { useAgentQuery } from '../../queries/agents';
import { useCreateThreadMutation, useThreadsQuery } from '../../queries/threads';

type Props = {
  newThreadStartingMesssage: string;
  children: ReactNode;
};

const ThreadsToggle = styled(Button)<{ $expanded?: boolean }>`
  display: ${({ $expanded }) => ($expanded ? 'none' : 'block')};
  position: relative;
  z-index: ${({ theme }) => theme.zIndex.dropdown - 1};
`;

const Container = styled.header<{ $sidebarExpanded: boolean }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space.$16};
  height: ${({ theme }) => theme.sizes.$64};
  padding: ${({ theme }) => theme.space.$14} ${({ theme }) => theme.space.$20};
  padding-left: ${({ theme, $sidebarExpanded }) => (!$sidebarExpanded ? theme.space.$64 : theme.space.$20)};
  outline: 1px solid ${({ theme }) => theme.colors.border.primary.color};

  ${({ theme }) => theme.screen.m} {
    height: 52px;
    padding-left: 52px;
  }
`;

export const ThreadHeader: FC<Props> = ({ children, newThreadStartingMesssage }) => {
  const navigate = useNavigate();
  const { agentId } = useParams('/thread/$agentId/$threadId');
  const { triggerProps, triggerRef } = useSidebarMenu('threads-list');
  const { expanded: mainMenuExpanded } = useSidebarMenu('main-menu');
  const { addSnackbar } = useSnackbar();

  const { mutate: createThread, isPending: isCreatingThread } = useCreateThreadMutation({ agentId });
  const { data: threads } = useThreadsQuery({ agentId });

  const { data: agent, isLoading } = useAgentQuery({ agentId });

  const onNewThread = async () => {
    const name = threads ? `Chat ${(threads?.length || 0) + 1}` : 'New chat';
    createThread(
      { name, startingMessage: newThreadStartingMesssage },
      {
        onSuccess: (data) => {
          if (data?.thread_id) {
            navigate({
              to: '/thread/$agentId/$threadId',
              params: { threadId: data.thread_id, agentId },
            });
          }
        },
        onError: () => {
          addSnackbar({
            message: 'Failed to create thread',
            variant: 'danger',
          });
        },
      },
    );
  };

  if (isLoading || !agent) {
    return null;
  }

  return (
    <Container $sidebarExpanded={mainMenuExpanded}>
      <ThreadsToggle
        variant="ghost-subtle"
        icon={IconLayoutRight}
        aria-label="Toggle thread view"
        {...triggerProps}
        ref={triggerRef}
      />
      <Box display="flex" alignItems="center" gap="$12">
        <AgentIcon mode="conversational" size="s" />
        <Typography variant="body-large" fontWeight="medium">
          {agent.name}
        </Typography>
      </Box>
      <Box display="flex" alignItems="center" gap="$8" ml="auto">
        {agent.metadata?.mode === 'conversational' && (
          <Tooltip text="New Thread" placement="bottom">
            <SideNavigation.Item
              icon={IconWriteNote}
              disabled={isCreatingThread}
              round
              aria-label="New Thread"
              onClick={onNewThread}
            />
          </Tooltip>
        )}
        {children}
      </Box>
    </Container>
  );
};
