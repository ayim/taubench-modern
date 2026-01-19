import { Box, Button, SideNavigation, Tooltip, Typography, useScreenSize } from '@sema4ai/components';
import { IconClock, IconMenu, IconPlus } from '@sema4ai/icons';
import { AgentIcon, useSidebarMenu } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { FC, ReactNode } from 'react';
import { useLinkProps } from '../../common/link';
import { useFeatureFlag, useNavigate, useParams } from '../../hooks';
import { useAgentQuery } from '../../queries';
import { Container as HeaderContainer, MenuToggleButton } from '../ThreadHeader';
import { AgentContextMenu } from '../Agents';
import { SparUIFeatureFlag } from '../../api';

type Props = {
  children: ReactNode;
  leftAction?: ReactNode;
};

const WorkItemsToggleButton = styled(Button)<{ $expanded?: boolean }>`
  display: ${({ $expanded }) => ($expanded ? 'none' : 'block')};
  position: relative;
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

const WorkItemsToggle = () => {
  const { expanded, triggerProps, triggerRef } = useSidebarMenu('work-items-list');
  const isMobile = useScreenSize('m');

  const showWorkItemsToggle = !expanded || isMobile;
  return (
    <WorkItemsToggleButton
      variant={expanded ? 'ghost-subtle' : 'ghost'}
      icon={IconClock}
      aria-label="Toggle work item view"
      {...triggerProps}
      ref={triggerRef}
      $expanded={!showWorkItemsToggle}
      aria-expanded={false}
    />
  );
};

export const WorkerHeader: FC<Props> = ({ children, leftAction }) => {
  const navigate = useNavigate();
  const { agentId } = useParams('/workItem/$agentId');

  const { expanded: mainMenuExpanded } = useSidebarMenu('main-menu');

  const { data: agent, isLoading } = useAgentQuery({ agentId });

  const createWorkItemLinkProps = useLinkProps('/workItem/$agentId/create', { agentId });
  const { enabled: isChatInteractive } = useFeatureFlag(SparUIFeatureFlag.agentChatInput);

  const onAgentDelete = () => {
    navigate({ to: '/home', params: {} });
  };

  if (isLoading || !agent) {
    return null;
  }

  return (
    <HeaderContainer $sidebarExpanded={mainMenuExpanded}>
      <MenuToggle />
      <WorkItemsToggle />

      <Box display="flex" alignItems="center" minWidth={0}>
        <Box display="flex" alignItems="center" gap="$8">
          <Box flexShrink={0}>
            <AgentIcon mode="worker" size="s" identifier={agent.id || ''} />
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
      {leftAction}
      <Box display="flex" alignItems="center" gap="$12" ml="auto">
        <Tooltip text="New Work Item" placement="bottom">
          {isChatInteractive ? (
            <SideNavigation.Item as="a" icon={IconPlus} round aria-label="New Work Item" {...createWorkItemLinkProps} />
          ) : (
            <SideNavigation.Item as="button" icon={IconPlus} round aria-label="New Work Item" disabled />
          )}
        </Tooltip>
        {children}
      </Box>
    </HeaderContainer>
  );
};
