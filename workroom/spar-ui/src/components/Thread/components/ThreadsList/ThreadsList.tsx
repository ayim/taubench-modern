import { FC, useEffect, useState, useRef } from 'react';
import { Box, Button, Menu, Typography } from '@sema4ai/components';
import { SidebarMenu } from '@sema4ai/layouts';

import { useQueries } from '@tanstack/react-query';
import { IconChevronDown, IconChevronRight, IconFilters, IconTrash } from '@sema4ai/icons';
import { useParams } from '../../../../hooks';
import { useThreadsQuery } from '../../../../queries/threads';
import { useListScenariosQuery, scenarioRunsQueryOptions } from '../../../../queries/evals';
import { useSparUIContext } from '../../../../api/context';
import { ThreadItem } from '../ThreadItem';
import { EvaluationFiltersComponent, type EvaluationFilters } from '../EvaluationFilters';
import { getMatchingScenarioIds } from './utils';
import { Header, SectionHeader, ScrollableContainer, ResizeHandle, AnimatedSection, AnimatedEvalSection } from './styles';

const defaultFilters: EvaluationFilters = {
  timeRange: 'all',
  models: [],
  architectures: [],
}

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
  const [isMessagesExpanded, setIsMessagesExpanded] = useState(true);
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

  const handleToggleMessages = () => {
    setIsMessagesExpanded(!isMessagesExpanded);
  };

  const handleToggleEvalRuns = () => {
    if (!isEvalRunsExpanded) {
      setEvalSectionHeight('200px');
    }
    setIsEvalRunsExpanded(!isEvalRunsExpanded);
  };

  // TODO-V2: Loading state for panels?
  if (isLoading) {
    return null;
  }

  const userInitiatedThreads = threads?.filter((thread) => !thread.metadata?.scenario_id);
  const allSimulationThreads = threads?.filter((thread) => !!thread.metadata?.scenario_id);

  const matchingScenarioIds = getMatchingScenarioIds(evaluationData.evaluations, evaluationFilters);
  
  const hasActiveFilters = evaluationFilters.timeRange !== 'all' || evaluationFilters.models.length > 0 || evaluationFilters.architectures.length > 0;

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


  return (
    <SidebarMenu name="threads-list" title="Threads list">
      <Box ref={containerRef} display="flex" flexDirection="column" height="100%" overflow="hidden">
         <Header>
             <Typography variant="body-medium" fontWeight="bold">
               History
             </Typography>
         </Header>
         <Box display="flex" flexDirection="column" flex="1" minHeight="0" overflow="hidden">
           <SectionHeader onClick={handleToggleMessages}>
             <Typography variant="body-medium" fontWeight="medium">
               Threads
             </Typography>
             <Button
               variant="ghost"
               size="small"
               icon={isMessagesExpanded ? IconChevronDown : IconChevronRight}
               onClick={handleToggleMessages}
               aria-label={isMessagesExpanded ? 'Collapse messages' : 'Expand messages'}
             />
          </SectionHeader>
          <AnimatedSection isExpanded={isMessagesExpanded}>
            <ScrollableContainer style={{ flex: 1, minHeight: 0 }}>
              {userInitiatedThreads?.map((thread) => (
                <ThreadItem 
                  key={thread.thread_id} 
                  threadId={thread.thread_id || ''} 
                  name={thread.name} 
                  scenarioId={thread.metadata?.scenario_id as string ?? null} 
                />
              ))}
              {userInitiatedThreads?.length === 0 && (
                <Box p="$12">
                  <Typography variant="body-small">
                    No messages yet
                  </Typography>
                </Box>
              )}
            </ScrollableContainer>
          </AnimatedSection>
         </Box>

       {allSimulationThreads && allSimulationThreads.length > 0 && (
          <>
            {isEvalRunsExpanded && (
              <ResizeHandle 
                onMouseDown={handleResizeStart}
                aria-label="Resize evaluation runs section"
                type="button"
              />
            )}

            <Box 
              display="flex"
              flexDirection="column"
              minHeight="0%" 
              overflow="hidden"
            >
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
                          size='small'
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
                        scenarioId={thread.metadata?.scenario_id as string ?? null} 
                      />
                    ))
                  ) : (
                    <Box p="$8">
                      <Typography variant="body-small" color="content.subtle.light">
                        {hasActiveFilters 
                          ? 'No evaluation runs match the current filters'
                          : 'No evaluation runs yet'
                        }
                      </Typography>
                      {hasActiveFilters && (
                        <Box marginTop="$8">
                        <Button
                          variant="ghost-subtle"
                          size="small"
                          onClick={clearFilters}
                          icon={IconTrash}
                        >
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
