import { Box, Button, Input, Menu, Typography } from '@sema4ai/components';
import { SidebarMenu, useSidebarMenu } from '@sema4ai/layouts';
import { styled } from '@sema4ai/theme';
import { FC, useEffect, useMemo, useRef, useState } from 'react';

import { IconChevronDown, IconChevronRight, IconCloseSmall, IconFilters, IconSearch, IconTrash } from '@sema4ai/icons';
import { useQueries } from '@tanstack/react-query';
import { useSparUIContext } from '../../../../api/context';
import { useParams } from '../../../../hooks';
import { scenarioRunsQueryOptions, useListScenariosQuery } from '../../../../queries/evals';
import { useThreadsQuery } from '../../../../queries/threads';
import { EvaluationFiltersComponent, type EvaluationFilters } from '../EvaluationFilters';
import { NewThreadItem } from '../NewThreadItem';
import { ThreadItem } from '../ThreadItem';
import { AnimatedEvalSection, Header, ResizeHandle, ScrollableContainer, SectionHeader } from './styles';
import { getMatchingScenarioIds } from './utils';

const defaultFilters: EvaluationFilters = {
  timeRange: 'all',
  models: [],
  architectures: [],
};

const ThreadSearchButton = styled(Button)<{ $expanded: boolean }>`
  position: absolute;
  right: ${({ theme, $expanded }) => ($expanded ? theme.space.$48 : theme.space.$12)};
  top: ${({ theme }) => theme.space.$12};
`;

export const ThreadsList: FC = () => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const { data: threads, isLoading, refetch: refetchThreads } = useThreadsQuery({ agentId });
  const { sparAPIClient } = useSparUIContext();

  const { data: scenarios = [], isLoading: scenariosLoading } = useListScenariosQuery({ agentId });

  const allRunsQueries = useQueries({
    queries: scenarios.map((scenario) =>
      scenarioRunsQueryOptions({
        scenarioId: scenario.scenario_id,
        sparAPIClient,
      }),
    ),
  });

  const allRunsData = allRunsQueries.map((query) => query.data ?? null);
  const allRunsLoading = allRunsQueries.some((query) => query.isLoading);

  const evaluationData = {
    evaluations: scenarios.map((scenario, index) => ({
      scenario,
      allRuns: allRunsData[index] ?? [],
    })),
    loading: scenariosLoading || allRunsLoading,
  };
  const [isEvalRunsExpanded, setIsEvalRunsExpanded] = useState(true);
  const [evalSectionHeight, setEvalSectionHeight] = useState('200px');
  const [isResizing, setIsResizing] = useState(false);
  const [evaluationFilters, setEvaluationFilters] = useState<EvaluationFilters>(defaultFilters);
  const [isFilterMenuOpen, setIsFilterMenuOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const startYRef = useRef(0);
  const startHeightRef = useRef(0);

  /**
   * Sometimes it may happen that we are on some valid $threadId,
   * but react-query client does not have it's information in its cache
   * in that case refreshing the threads query so that new list will
   * containe the thread we are on
   */
  useEffect(() => {
    const hasThread = threads?.some((thread) => thread.thread_id === threadId);
    if (!hasThread) {
      refetchThreads();
    }
  }, [threadId]);

  // Handle mouse events for resizing
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !containerRef.current) return;

      const containerHeight = containerRef.current.clientHeight;
      const deltaY = e.clientY - startYRef.current;
      const newHeightPx = startHeightRef.current - deltaY;

      const minHeight = 50;
      const maxHeight = containerHeight * 0.9;
      const constrainedHeight = Math.min(Math.max(newHeightPx, minHeight), maxHeight);

      setEvalSectionHeight(`${constrainedHeight}px`);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  const handleResizeStart = (e: React.MouseEvent) => {
    if (!containerRef.current) return;

    setIsResizing(true);
    startYRef.current = e.clientY;

    let currentHeightPx: number;
    const containerHeight = containerRef.current.clientHeight;

    if (evalSectionHeight.includes('%')) {
      const currentPercentage = parseFloat(evalSectionHeight.replace('%', ''));
      currentHeightPx = (currentPercentage / 100) * containerHeight;
    } else {
      currentHeightPx = parseFloat(evalSectionHeight.replace('px', ''));
    }

    startHeightRef.current = currentHeightPx;
  };

  const handleToggleEvalRuns = () => {
    if (!isEvalRunsExpanded) {
      setEvalSectionHeight('200px');
    }
    setIsEvalRunsExpanded(!isEvalRunsExpanded);
  };

  const userInitiatedThreads = threads?.filter((thread) => !thread.metadata?.scenario_id);
  const allSimulationThreads = threads?.filter((thread) => !!thread.metadata?.scenario_id);

  const matchingScenarioIds = getMatchingScenarioIds(evaluationData.evaluations, evaluationFilters);

  const hasActiveFilters =
    evaluationFilters.timeRange !== 'all' ||
    evaluationFilters.models.length > 0 ||
    evaluationFilters.architectures.length > 0;

  const filteredSimulationThreads = allSimulationThreads?.filter((thread) => {
    const scenarioId = thread.metadata?.scenario_id as string;
    if (!scenarioId) {
      return true;
    }

    if (!hasActiveFilters) {
      return true;
    }

    return matchingScenarioIds.has(scenarioId);
  });

  const simulationThreads = filteredSimulationThreads || allSimulationThreads;

  const clearFilters = () => {
    setEvaluationFilters(defaultFilters);
    setIsFilterMenuOpen(false);
  };

  const { expanded: threadsListExpanded } = useSidebarMenu('threads-list');
  const [filteringThread, setFilteringThread] = useState(false);
  const [threadFilterText, setThreadFilterText] = useState('');

  const startThreadFilter = () => {
    setThreadFilterText('');
    setFilteringThread(true);
  };

  const stopThreadFilter = () => {
    setThreadFilterText('');
    setFilteringThread(false);
  };

  const filteredUserInitiatedThreads = useMemo(
    () =>
      userInitiatedThreads?.filter((thread) => {
        return thread.name.toLowerCase().includes(threadFilterText.toLowerCase().trim());
      }),
    [userInitiatedThreads, threadFilterText],
  );

  // TODO-V2: Loading state for panels?
  if (isLoading) {
    return null;
  }

  return (
    <SidebarMenu name="threads-list" title="Threads list">
      <Box ref={containerRef} display="flex" flexDirection="column" height="100%" overflow="hidden">
        <Header>
          <Typography variant="body-medium" fontWeight="bold">
            History
          </Typography>
        </Header>
        {!filteringThread && (
          <ThreadSearchButton
            $expanded={threadsListExpanded}
            variant="ghost-subtle"
            icon={IconSearch}
            onClick={startThreadFilter}
            aria-label="thread-search"
          />
        )}
        {filteringThread && (
          <Box px={1}>
            <Input
              autoFocus
              aria-label="thread-search-input"
              iconLeft={IconSearch}
              placeholder="Seach Chats"
              value={threadFilterText}
              onChange={(e) => setThreadFilterText(e.target.value)}
              iconRight={IconCloseSmall}
              onIconRightClick={stopThreadFilter}
              onKeyDown={(e) => {
                if (e.key === 'Escape') stopThreadFilter();
              }}
              onBlur={() => {
                if(!threadFilterText.trim()) stopThreadFilter();
              }}
              iconRightLabel="close-search"
              round
            />
          </Box>
        )}
        <NewThreadItem />
        <Box display="flex" flexDirection="column" flex="1" minHeight="0" overflow="hidden">
          <ScrollableContainer style={{ flex: 1, minHeight: 0 }}>
            {filteredUserInitiatedThreads?.map((thread) => (
              <ThreadItem
                key={thread.thread_id}
                threadId={thread.thread_id || ''}
                name={thread.name}
                scenarioId={(thread.metadata?.scenario_id as string) ?? null}
              />
            ))}
            {filteredUserInitiatedThreads?.length === 0 && (
              <Box p="$12">
                <Typography variant="body-small">{filteringThread ? 'No threads found' : 'No messages yet'}</Typography>
              </Box>
            )}
          </ScrollableContainer>
        </Box>

        {allSimulationThreads && allSimulationThreads.length > 0 && (
          <>
            {isEvalRunsExpanded && (
              <ResizeHandle onMouseDown={handleResizeStart} aria-label="Resize evaluation runs section" type="button" />
            )}

            <Box display="flex" flexDirection="column" minHeight="0%" overflow="hidden">
              <SectionHeader display="flex" alignItems="center" justifyContent="space-between">
                <Box onClick={handleToggleEvalRuns} style={{ cursor: 'pointer', flex: 1 }}>
                  <Typography variant="body-medium" fontWeight="medium">
                    Evaluation Runs
                  </Typography>
                </Box>
                <Box display="flex" alignItems="center" gap="$4">
                  {isEvalRunsExpanded && (
                    <Menu
                      visible={isFilterMenuOpen}
                      setVisible={setIsFilterMenuOpen}
                      trigger={
                        <Button
                          variant={hasActiveFilters ? 'secondary' : 'ghost-subtle'}
                          icon={IconFilters}
                          round
                          aria-label="Filter evaluation runs"
                          disabled={evaluationData.loading}
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                          }}
                        />
                      }
                    >
                      <Box minWidth="280px" maxHeight="400px" overflowY="auto">
                        <EvaluationFiltersComponent
                          evaluationData={evaluationData}
                          filters={evaluationFilters}
                          onFiltersChange={setEvaluationFilters}
                          onClearAll={clearFilters}
                        />
                      </Box>
                    </Menu>
                  )}
                  <Button
                    variant="ghost"
                    size="small"
                    icon={isEvalRunsExpanded ? IconChevronDown : IconChevronRight}
                    onClick={handleToggleEvalRuns}
                    aria-label={isEvalRunsExpanded ? 'Collapse evaluation runs' : 'Expand evaluation runs'}
                  />
                </Box>
              </SectionHeader>

              <AnimatedEvalSection
                isExpanded={isEvalRunsExpanded}
                height={isEvalRunsExpanded ? evalSectionHeight : '0px'}
                enableTransition={!isResizing}
              >
                <ScrollableContainer style={{ height: '100%' }}>
                  {simulationThreads && simulationThreads.length > 0 ? (
                    simulationThreads.map((thread) => (
                      <ThreadItem
                        key={thread.thread_id}
                        threadId={thread.thread_id || ''}
                        name={thread.name}
                        scenarioId={(thread.metadata?.scenario_id as string) ?? null}
                      />
                    ))
                  ) : (
                    <Box p="$8">
                      <Typography variant="body-small" color="content.subtle.light">
                        {hasActiveFilters ? 'No evaluation runs match the current filters' : 'No evaluation runs yet'}
                      </Typography>
                      {hasActiveFilters && (
                        <Box marginTop="$8">
                          <Button variant="ghost-subtle" size="small" onClick={clearFilters} icon={IconTrash}>
                            Clear filters
                          </Button>
                        </Box>
                      )}
                    </Box>
                  )}
                </ScrollableContainer>
              </AnimatedEvalSection>
            </Box>
          </>
        )}
      </Box>
    </SidebarMenu>
  );
};
