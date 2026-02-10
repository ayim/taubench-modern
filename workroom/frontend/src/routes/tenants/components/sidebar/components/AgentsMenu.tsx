import { type DragEvent, type MouseEvent, type ReactNode, useEffect, useState } from 'react';
import { Box, Button, Typography } from '@sema4ai/components';
import { IconCloseSmall } from '@sema4ai/icons';
import { AgentIcon } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { useParams, useRouteContext } from '@tanstack/react-router';

import { AgentContextMenu } from '~/components/Agents/AgentContextMenu';
import { RouterSideNavigationLink } from '~/components/RouterLink';
import { useAgentsQuery } from '~/queries/agents';
import { isConversationalAgent } from '~/utils';
import { ADMINISTRATION_ACCESS_PERMISSION } from '~/lib/userPermissions';
import { useAgentPreferencesStore, selectFavourites, selectRecentAgents } from '~/hooks/useAgentPreferencesStore';

const MIN_RECENT_VISIBLE = 5;
const TARGET_TOTAL_VISIBLE = 10;

const AgentsMenuContainer = styled(Box)`
  border-top: 1px solid ${({ theme }) => theme.colors.border.subtle.color};
  padding-top: ${({ theme }) => theme.space.$12};
  margin-top: ${({ theme }) => theme.space.$12};
`;

const SectionLabel = styled(Typography)`
  padding: ${({ theme }) => theme.space.$8} ${({ theme }) => theme.space.$12};
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: ${({ theme }) => theme.colors.content.subtle.light};
`;

const DraggableItem = styled(Box)<{ $isDragging?: boolean }>`
  opacity: ${({ $isDragging }) => ($isDragging ? 0.4 : 1)};
  transition: transform 200ms ease;
`;

const ShowMoreButton = styled(Button)`
  margin: ${({ theme }) => theme.space.$4} ${({ theme }) => theme.space.$12};
  align-self: flex-start;
`;

export const AgentsMenu = () => {
  const { tenantId } = useParams({ from: '/tenants/$tenantId' });
  const { permissions } = useRouteContext({ from: '/tenants/$tenantId' });
  const { data: agents } = useAgentsQuery({});

  const favourites = useAgentPreferencesStore((s) => selectFavourites(s, tenantId));
  const recentAgents = useAgentPreferencesStore((s) => selectRecentAgents(s, tenantId));
  const { reorderFavourites, removeFavourite, cleanupStaleAgents } = useAgentPreferencesStore();

  const [draggedAgentId, setDraggedAgentId] = useState<string | null>(null);
  const [showAllRecent, setShowAllRecent] = useState(false);

  useEffect(() => {
    if (!agents) {
      return;
    }
    const validIds = new Set(agents.map((a) => a.id).filter((id): id is string => !!id));
    cleanupStaleAgents(tenantId, validIds);
  }, [agents, tenantId, cleanupStaleAgents]);

  if (!agents) {
    return null;
  }

  const agentMap = new Map(agents.map((a) => [a.id, a]));
  const favouriteAgents = favourites.map((id) => agentMap.get(id)).filter((a): a is NonNullable<typeof a> => !!a);
  const favouriteIds = new Set(favourites);

  const recentAgentEntries = recentAgents
    .filter((r) => !favouriteIds.has(r.agentId) && agentMap.has(r.agentId))
    .map((r) => agentMap.get(r.agentId)!);

  const recentLimit = Math.max(MIN_RECENT_VISIBLE, TARGET_TOTAL_VISIBLE - favouriteAgents.length);
  const hasMoreRecent = recentAgentEntries.length > recentLimit;
  const visibleRecent = showAllRecent ? recentAgentEntries : recentAgentEntries.slice(0, recentLimit);

  const handleDragStart = (e: DragEvent, agentId: string) => {
    setDraggedAgentId(agentId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: DragEvent, targetIndex: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (draggedAgentId === null) {
      return;
    }
    const currentIndex = favourites.indexOf(draggedAgentId);
    if (currentIndex !== -1 && currentIndex !== targetIndex) {
      reorderFavourites(tenantId, currentIndex, targetIndex);
    }
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDraggedAgentId(null);
  };

  const handleDragEnd = () => {
    setDraggedAgentId(null);
  };

  const renderAgentLink = (agent: (typeof agents)[number], action?: ReactNode) => {
    if (!agent.id) {
      return null;
    }

    const isConversational = isConversationalAgent(agent);
    const mode = isConversational ? 'conversational' : 'worker';
    const route = isConversational
      ? '/tenants/$tenantId/conversational/$agentId'
      : '/tenants/$tenantId/worker/$agentId';

    const defaultAction = permissions[ADMINISTRATION_ACCESS_PERMISSION] ? <AgentContextMenu agent={agent} /> : null;

    return (
      <RouterSideNavigationLink
        icon={<AgentIcon mode={mode} size="s" identifier={agent.id} />}
        key={agent.id}
        to={route}
        params={{ tenantId, agentId: agent.id }}
        action={action !== undefined ? action : defaultAction}
      >
        {agent.name}
      </RouterSideNavigationLink>
    );
  };

  const hasFavourites = favouriteAgents.length > 0;
  const hasRecent = recentAgentEntries.length > 0;

  if (!hasFavourites && !hasRecent) {
    return null;
  }

  return (
    <AgentsMenuContainer display="flex" flexDirection="column">
      {hasFavourites && (
        <>
          <SectionLabel variant="body-small" fontWeight="medium">
            Favourites
          </SectionLabel>
          {favouriteAgents.map((agent, index) => {
            const agentId = agent.id;
            if (!agentId) {
              return null;
            }
            return (
              <DraggableItem
                key={agentId}
                $isDragging={draggedAgentId === agentId}
                draggable
                onDragStart={(e: DragEvent) => handleDragStart(e, agentId)}
                onDragOver={(e: DragEvent) => handleDragOver(e, index)}
                onDrop={handleDrop}
                onDragEnd={handleDragEnd}
              >
                {renderAgentLink(
                  agent,
                  <Button
                    icon={IconCloseSmall}
                    variant="ghost"
                    size="small"
                    round
                    aria-label="Remove from favourites"
                    onClick={(e: MouseEvent) => {
                      e.preventDefault();
                      removeFavourite(tenantId, agentId);
                    }}
                  />,
                )}
              </DraggableItem>
            );
          })}
        </>
      )}

      {hasRecent && (
        <>
          <SectionLabel variant="body-small" fontWeight="medium">
            Recent
          </SectionLabel>
          {visibleRecent.map((agent) => renderAgentLink(agent))}
          {hasMoreRecent && (
            <ShowMoreButton variant="ghost-subtle" size="small" onClick={() => setShowAllRecent((prev) => !prev)}>
              {showAllRecent ? 'Show less' : 'Show more'}
            </ShowMoreButton>
          )}
        </>
      )}
    </AgentsMenuContainer>
  );
};
