import { Box, Button, SideNavigation, Tooltip, Typography, useScreenSize } from '@sema4ai/components';
import { IconClock, IconMenu, IconPlus, IconStar } from '@sema4ai/icons';
import { AgentIcon, useSidebarMenu } from '@sema4ai/layouts';
import { useNavigate, useParams } from '@tanstack/react-router';
import { styled } from '@sema4ai/theme';
import { FC, ReactNode } from 'react';
import { useLinkProps } from '~/components/link';
import { useAgentQuery } from '~/queries/agents';
import { useAgentPreferencesStore } from '~/hooks/useAgentPreferencesStore';
import { FavouriteButton } from '../FavouriteButton';
import { useFeatureFlag, FeatureFlag } from '../../hooks';
import { Container as HeaderContainer, MenuToggleButton } from '../ThreadHeader';
import { AgentContextMenu } from '../Agents';

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
  const { agentId = '', tenantId = '' } = useParams({ strict: false });

  const { expanded: mainMenuExpanded } = useSidebarMenu('main-menu');

  const { data: agent, isLoading } = useAgentQuery({ agentId });
  const { addFavourite, removeFavourite } = useAgentPreferencesStore();
  const favourites = useAgentPreferencesStore((s) => s.favouritesByTenant[tenantId] ?? []);

  const createWorkItemLinkProps = useLinkProps('/tenants/$tenantId/worker/$agentId/create', { agentId, tenantId });
  const agentIsFavourite = favourites.includes(agentId);
  const { enabled: isChatInteractive } = useFeatureFlag(FeatureFlag.agentChatInput);

  const onAgentDelete = () => {
    navigate({ to: '/tenants/$tenantId/home', params: { tenantId } });
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
        <Tooltip text={agentIsFavourite ? 'Remove from favourites' : 'Add to favourites'} placement="bottom">
          <FavouriteButton
            icon={IconStar}
            variant="ghost"
            size="small"
            round
            $active={agentIsFavourite}
            aria-label={agentIsFavourite ? 'Remove from favourites' : 'Add to favourites'}
            onClick={() => (agentIsFavourite ? removeFavourite(tenantId, agentId) : addFavourite(tenantId, agentId))}
          />
        </Tooltip>
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
