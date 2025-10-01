import { Box, Button, SideNavigation, Tooltip, Typography } from '@sema4ai/components';
import { IconLayoutRight, IconPlus } from '@sema4ai/icons';
import { AgentIcon, useSidebarMenu } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { FC, ReactNode } from 'react';
import { useLinkProps } from '../../common/link';
import { useParams } from '../../hooks';
import { useAgentQuery } from '../../queries';
import { Container as HeaderContainer } from '../ThreadHeader';

type Props = {
  children: ReactNode;
};

const WorkItemsToggle = styled(Button)<{ $expanded?: boolean }>`
  display: ${({ $expanded }) => ($expanded ? 'none' : 'block')};
  position: relative;
`;

export const WorkerHeader: FC<Props> = ({ children }) => {
  const { agentId } = useParams('/workItem/$agentId');

  const { triggerProps, triggerRef } = useSidebarMenu('work-items-list');
  const { expanded: mainMenuExpanded } = useSidebarMenu('main-menu');

  const { data: agent, isLoading } = useAgentQuery({ agentId });

  const createWorkItemLinkProps = useLinkProps('/workItem/$agentId/create', { agentId });

  if (isLoading || !agent) {
    return null;
  }

  return (
    <HeaderContainer $sidebarExpanded={mainMenuExpanded}>
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
          <SideNavigation.Item as="a" icon={IconPlus} round aria-label="New Work Item" {...createWorkItemLinkProps} />
        </Tooltip>
        {children}
      </Box>
    </HeaderContainer>
  );
};
