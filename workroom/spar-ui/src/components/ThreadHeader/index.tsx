import { Box, Button, SideNavigation, Tooltip, Typography, useScreenSize } from '@sema4ai/components';
import { IconClock, IconMenu, IconWriteNote } from '@sema4ai/icons';
import { AgentIcon, useSidebarMenu } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { FC, ReactNode } from 'react';

import { useFeatureFlag, useNavigate, useParams } from '../../hooks';
import { useCreateThread } from '../../hooks/useCreateThread';
import { useAgentQuery } from '../../queries/agents';
import { useThreadQuery } from '../../queries/threads';
import { ThreadSearch } from '../ThreadSearch';
import { AgentContextMenu } from '../Agents';
import { SparUIFeatureFlag } from '../../api';

type Props = {
  children: ReactNode;
};

export const MenuToggleButton = styled(Button)`
  position: relative;
`;

const ThreadsToggleButton = styled(Button)<{ $expanded?: boolean }>`
  display: ${({ $expanded }) => ($expanded ? 'none' : 'block')};
  position: relative;
`;

export const Container = styled.header<{ $sidebarExpanded: boolean }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.space.$16};
  height: ${({ theme }) => theme.sizes.$64};
  padding: ${({ theme }) => theme.space.$14} ${({ theme }) => theme.space.$20};

  ${({ theme }) => theme.screen.m} {
    height: 52px;
  }
`;

const MenuToggle = () => {
  const { expanded, triggerProps, triggerRef } = useSidebarMenu('main-menu');
  const isMobile = useScreenSize('m');

  const showMenuToggle = !expanded || isMobile;
  if (!showMenuToggle) {
    return null;
  }

  return (
    <MenuToggleButton
      ref={triggerRef}
      {...triggerProps}
      icon={IconMenu}
      variant={expanded ? 'ghost-subtle' : 'ghost'}
      aria-label="Toggle main menu"
      aria-expanded={false}
    />
  );
};

const ThreadsToggle = () => {
  const { expanded, triggerProps, triggerRef } = useSidebarMenu('threads-list');
  const isMobile = useScreenSize('m');

  const showThreadsToggle = !expanded || isMobile;
  return (
    <ThreadsToggleButton
      variant={expanded ? 'ghost-subtle' : 'ghost'}
      icon={IconClock}
      aria-label="Toggle thread view"
      {...triggerProps}
      ref={triggerRef}
      $expanded={!showThreadsToggle}
      aria-expanded={false}
    />
  );
};

export const ThreadHeader: FC<Props> = ({ children }) => {
  const navigate = useNavigate();
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const { expanded: mainMenuExpanded } = useSidebarMenu('main-menu');
  const { onNewThread, isCreatingThread } = useCreateThread();
  const { enabled: isChatInteractive } = useFeatureFlag(SparUIFeatureFlag.agentChatInput);

  const { data: agent, isLoading } = useAgentQuery({ agentId });
  const { data: thread } = useThreadQuery({ threadId });

  // Check if this is an evaluation thread (has scenario_id in metadata)
  const isEvaluationThread = Boolean(thread?.metadata?.scenario_id);

  const onAgentDelete = () => {
    navigate({ to: '/home', params: {} });
  };

  if (isLoading || !agent) {
    return null;
  }

  const isNewThreadDisabled = isCreatingThread || !isChatInteractive;
  return (
    <Container $sidebarExpanded={mainMenuExpanded}>
      <MenuToggle />

      {/* Hide threads list toggle for evaluation threads - navigation only through eval sidebar */}
      {!isEvaluationThread && <ThreadsToggle />}
      <Box display="flex" alignItems="center" minWidth={0}>
        <Box display="flex" alignItems="center" gap="$8">
          <Box flexShrink={0}>
            <AgentIcon mode="conversational" size="s" identifier={agent.id || ''} />
          </Box>
          <Box maxWidth="100%" overflow="hidden">
            <Typography variant="body-large" fontWeight="medium" $nowrap truncate={1}>
              {agent.name}
            </Typography>
          </Box>
        </Box>
        <Box ml="$4">
          <AgentContextMenu agent={agent} onAgentDelete={onAgentDelete} />
        </Box>
      </Box>
      <Box display="flex" alignItems="center" gap="$12" ml="auto">
        {/* Hide new chat button for evaluation threads */}
        {!isEvaluationThread && (
          <Tooltip text="New Conversation" placement="bottom">
            <SideNavigation.Item
              icon={IconWriteNote}
              disabled={isNewThreadDisabled}
              round
              aria-label="New Conversation"
              onClick={onNewThread}
            />
          </Tooltip>
        )}
        {children}
        <ThreadSearch />
      </Box>
    </Container>
  );
};
