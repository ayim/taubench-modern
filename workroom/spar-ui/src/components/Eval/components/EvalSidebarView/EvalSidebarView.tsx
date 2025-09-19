import React, { FC, useMemo, useState } from 'react';
import { Box, Button, Typography, Badge, Progress, Menu, Tooltip, Divider, useSnackbar, Dialog } from '@sema4ai/components';
import {
  IconChemicalBottle,
  IconPlay,
  IconPlus,
  IconDotsHorizontal,
  IconChevronDown,
  IconChevronRight,
  IconSendSmall,
  IconInformation,
  IconShare,
  IconLightBulb,
  IconDownload,
  IconStatusCompleted,
  IconStatusError,
  IconStatusPending,
  IconChevronUp,
  IconTrash,
} from '@sema4ai/icons';
import { useQueries, useQueryClient } from '@tanstack/react-query';
import { useThreadMessagesQuery } from '../../../../queries';
import { useNavigate, useParams } from '../../../../hooks';
import { useSparUIContext } from '../../../../api/context';
import { getRunStatus, getBadgeIcon, getIconColor, getBadgeColor, getStatusLabel, getEvaluationResultColor, getEvaluationResultLabel, getTrialOverallStatus, getEvaluationResultIcon } from './utils';
import { latestScenarioRunQueryOptions, useCreateScenarioMutation, useCreateScenarioRunMutation, useDeleteScenarioMutation, useListScenariosQuery, usePollScenarioRun, useSuggestScenarioMutation } from '../../../../queries/evals';
import { CreateEvalDialog, CreateEvalFormData } from '../CreateEvalDialog';
import { transformAgentServerScenarios } from '../../../../lib/Evals';

export interface EvalSidebarViewProps {
  agentId: string;
  onDownloadJSON: (
    data: unknown,
    options: {
      filename: string;
      addTimestamp?: boolean;
    },
  ) => void;
}

export const EvalSidebarView: FC<EvalSidebarViewProps> = ({
  agentId,
  onDownloadJSON,
}) => {
  const [deleteTarget, setDeleteTarget] = useState<{ scenarioId: string; name: string } | null>(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [suggestedValues, setSuggestedValues] = useState<Partial<CreateEvalFormData> | undefined>(undefined);
  const [isFetchingSuggestion, setIsFetchingSuggestion] = useState(false);
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set());
  const [expandedTrials, setExpandedTrials] = useState<Set<string>>(new Set());
  const [expandedEvaluations, setExpandedEvaluations] = useState<Set<string>>(new Set());
  const [selectedTrials, setSelectedTrials] = useState<Map<string, number>>(new Map());
  const [selectedTrialsForAll, setSelectedTrialsForAll] = useState<number>(1);
  
  
  const { threadId } = useParams('/thread/$agentId/$threadId');
  const { data: messages = [] } = useThreadMessagesQuery({
    threadId,
  });
  
  const queryClient = useQueryClient();
  const { addSnackbar } = useSnackbar();
  const { sparAPIClient } = useSparUIContext();
  const navigate = useNavigate();
  
  const deleteScenarioMutation = useDeleteScenarioMutation({});
  const createScenarioRunMutation = useCreateScenarioRunMutation({});
  const { pollForCompletion } = usePollScenarioRun();
  const createScenarioMutation = useCreateScenarioMutation({});
  const suggestScenarioMutation = useSuggestScenarioMutation({});
  const { data: scenarios = [], isLoading: scenariosLoading } = useListScenariosQuery({
    agentId,
  });
  
  const latestRunQueries = useQueries({
    queries: scenarios.map((scenario) =>
      latestScenarioRunQueryOptions({
        scenarioId: scenario.scenario_id,
        sparAPIClient,
      }),
    ),
  });
  const latestRunsData = latestRunQueries.map((query) => query.data ?? null);
  const latestRunsLoading = latestRunQueries.some((query) => query.isLoading);
  const loading = scenariosLoading || latestRunsLoading;
  
  const evaluations = useMemo(() => {
    return transformAgentServerScenarios(scenarios, latestRunsData);
  }, [scenarios, latestRunsData]);
  const isAnyTestRunning = evaluations.some(evaluation => evaluation.isRunning);
  
  const handleCreateEvaluation = async (data: CreateEvalFormData) => {
    await createScenarioMutation.mutateAsync({
      body: {
        name: data.name,
        description: data.description,
        thread_id: threadId,
      },
    });
    setCreateDialogOpen(false);
    setSuggestedValues(undefined);
    setIsFetchingSuggestion(false);
  };

  const handleAddEvaluation = async () => {
    setCreateDialogOpen(true);
    setIsFetchingSuggestion(true);
    setSuggestedValues(undefined);

    try {
      const suggestion = await suggestScenarioMutation.mutateAsync({
        body: {
          thread_id: threadId,
          max_options: 1,
        },
      });

      setSuggestedValues({
        name: suggestion.name,
        description: suggestion.description,
      });
    } catch (_error) {
      addSnackbar({
        message: 'Could not generate suggestion, but you can still create an evaluation manually',
        variant: 'danger',
      });
      setSuggestedValues(undefined);
    } finally {
      setIsFetchingSuggestion(false);
    }
  };

  const handleRunTest = async (
    scenario: {
      scenarioId: string;
      name: string;
      description: string;
      threadId: string | null;
    },
    numTrials: number = 1,
  ) => {
    try {
      await createScenarioRunMutation.mutateAsync({
        scenarioId: scenario.scenarioId,
        body: { num_trials: numTrials },
      });

      await pollForCompletion(scenario.scenarioId);

      await queryClient.invalidateQueries({ queryKey: ['threads', agentId] });
    } catch {
      addSnackbar({
        message: `Failed to run test for "${scenario.name}"`,
        variant: 'danger',
      });
    }
  };

  const handleRunAll = (numTrials: number = 1) => {
    evaluations.forEach(({ scenario }) => handleRunTest(scenario, numTrials));
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;

    await deleteScenarioMutation.mutateAsync({
      scenarioId: deleteTarget.scenarioId,
    });

    setDeleteTarget(null);
  };

  const handleDownloadScenario = (scenario: {
    scenarioId: string;
    name: string;
    description: string;
    threadId: string | null;
  }) => {
    const evaluation = evaluations.find((evaluationItem) => evaluationItem.scenario.scenarioId === scenario.scenarioId);

    if (!evaluation) {
      addSnackbar({
        message: 'Scenario data not found',
        variant: 'danger',
      });
      return;
    }

    const scenarioData = {
      scenario: evaluation.scenario,
      latestRun: evaluation.latestRun,
    };

    const filename = `${scenario.name.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_scenario`;

    onDownloadJSON(scenarioData, {
      filename,
      addTimestamp: true,
    });

    addSnackbar({
      message: `Scenario "${scenario.name}" downloaded successfully`,
      variant: 'success',
    });
  };

  const handleViewResults = (trial: { threadId: string }) => {
    if (trial.threadId) {
      navigate({
        to: '/thread/$agentId/$threadId',
        params: {
          agentId,
          threadId: trial.threadId,
        },
      });
    }
  };

  const toggleResults = (scenarioId: string) => {
    setExpandedResults((prev) => {
      if (prev.has(scenarioId)) {
        const next = new Set(prev);
        next.delete(scenarioId);
        return next;
      }
      return new Set([...prev, scenarioId]);
    });
  };

  const toggleTrialDetails = (trialKey: string) => {
    setExpandedTrials((prev) => {
      if (prev.has(trialKey)) {
        const next = new Set(prev);
        next.delete(trialKey);
        return next;
      }
      return new Set([...prev, trialKey]);
    });
  };

  const toggleEvaluationDetails = (evaluationKey: string) => {
    setExpandedEvaluations((prev) => {
      if (prev.has(evaluationKey)) {
        const next = new Set(prev);
        next.delete(evaluationKey);
        return next;
      }
      return new Set([...prev, evaluationKey]);
    });
  };

  const getSelectedTrialsForScenario = (scenarioId: string) => selectedTrials.get(scenarioId) || 1;
  const getRunTestButtonText = (scenarioId: string) => {
    const numTrials = getSelectedTrialsForScenario(scenarioId);
    return numTrials === 1 ? 'Run Test' : `Run Test (${numTrials}x)`;
  };
  const getRunAllButtonText = () => {
    return selectedTrialsForAll === 1 ? 'Run All Tests' : `Run All Tests (${selectedTrialsForAll}x)`;
  };

  if (loading) {
    return (
      <Box display="flex" flexDirection="column" gap="$16" padding="$16" height="100%">
        <Box display="flex" alignItems="center" justifyContent="center" flex="1">
          <Progress />
        </Box>
      </Box>
    );
  }

  return (
    <>
      <Box display="flex" flexDirection="column" gap="$16" padding="$16" height="100%" overflow="hidden">
        {/* Header */}
        <Box display="flex" flexDirection="column" gap="$8" flexShrink="0">
          <Box display="flex" alignItems="center" gap="$8">
          <Typography variant="display-small">Evaluations</Typography>
          <Tooltip text="Evaluations are used to test the performance of your agent.">
          <IconInformation size="48" color='content.subtle.light' />
          </Tooltip>
          </Box>
          <Typography variant="body-medium">
            All evaluations run will be shown here.
          </Typography>
          <Box display="flex" justifyContent="flex-start" paddingTop="$8" mb="$8">
            {messages.length < 2 ? (
              <Box backgroundColor="yellow20" padding="$20" borderRadius="$12" display="flex" alignItems="center" gap="$8">
              <IconLightBulb size={24} />
              <Typography variant="body-medium">
                Talk to your agent to be able to add an evaluation.
              </Typography>
              </Box>
            ) : (
              <Button variant="outline" round onClick={handleAddEvaluation} disabled={messages.length === 0}>
              <IconPlus size="16" />
              Add Evaluation
            </Button>
            )}
          </Box>
          <Divider />
        </Box>

        {/* Scenarios List */}
        <Box display="flex" flexDirection="column" gap="$12" flex="1" overflow="auto" minHeight="0">
          {evaluations.length === 0 ? (
            <Box display="flex" flexDirection="column" alignItems="center" gap="$12" padding="$24">
              <IconChemicalBottle size="48" />
              <Box textAlign="center">
                <Typography variant="body-large">No evaluations yet</Typography>
                <Typography variant="body-medium">
                  Create your first evaluation to get started
                </Typography>
              </Box>
            </Box>
          ) : (
            evaluations.map(({ scenario, latestRun, isRunning }) => {
              const runStatus = isRunning ? 'EXECUTING' : (latestRun && getRunStatus(latestRun.trials));

              return (
                <Box
                  key={scenario.scenarioId}
                  display="flex"
                  flexDirection="column"
                  gap="$8"
                  mt="$16"
                >
                  <Box display="flex" flexDirection="column" gap="$8">
                    <Box>
                      <Box display="flex" alignItems="center" gap="$8">
                        <IconChemicalBottle size={20} />
                        <Typography variant="display-headline">{scenario.name}</Typography>
                      </Box>
                        <Typography variant="body-small" mt="$8">
                          {scenario.description}
                        </Typography>
                    </Box>
                    <Box width="100%" display="flex" alignItems="center" gap="$8">
                      <Button
                        variant="outline"
                        round
                        disabled={isRunning || isAnyTestRunning}
                        loading={isRunning}
                        icon={IconPlay}
                        onClick={() => handleRunTest(scenario, getSelectedTrialsForScenario(scenario.scenarioId))}
                      >
                        {getRunTestButtonText(scenario.scenarioId)}
                      </Button>
                      <Box>
                        <Menu
                          trigger={
                            <Button
                              variant="outline"
                              icon={IconDotsHorizontal}
                              round
                              aria-label="Scenario actions"
                              disabled={isAnyTestRunning}
                            />
                          }
                          >
                            {getSelectedTrialsForScenario(scenario.scenarioId) === 4 ? (
                              <Tooltip text='Run tests 1 time when clicking "Run Test"'>
                              <Menu.Item
                                onClick={() => {
                                  setSelectedTrials(prev => new Map(prev).set(scenario.scenarioId, 1));
                                }}
                                icon={IconInformation}
                              >
                                Switch to 1x
                                </Menu.Item>
                                </Tooltip>
                            ) : (
                              <Tooltip text='Run tests 4 times when clicking "Run Test"'>
                              <Menu.Item
                                onClick={() => {
                                  setSelectedTrials(prev => new Map(prev).set(scenario.scenarioId, 4));
                                }}
                                icon={IconInformation}
                              >
                                Switch to 4x
                              </Menu.Item>
                                  </Tooltip>
                            )}
                            <Menu.Item 
                              icon={IconDownload}
                              onClick={() => handleDownloadScenario(scenario)}
                            >
                              Download JSON
                            </Menu.Item>
                            <Menu.Item icon={IconTrash} onClick={() => setDeleteTarget({ scenarioId: scenario.scenarioId, name: scenario.name })}>Delete</Menu.Item>
                          </Menu>
                      </Box>
                      {runStatus && (
                        <Box display="flex" alignItems="center" gap="$4">
                          {latestRun && !isRunning && latestRun.trials.some(trial => trial.status === 'COMPLETED' || trial.status === 'ERROR') ? (
                            <Badge
                              forwardedAs="button"
                              icon={getBadgeIcon(runStatus)}
                              iconColor={getIconColor(runStatus)}
                              aria-description="Status of the latest run"
                              variant={getBadgeColor(runStatus)}
                              label={getStatusLabel(runStatus)}
                              iconVisible
                              iconAfter={expandedResults.has(scenario.scenarioId) ? IconChevronUp : IconChevronDown}
                              onClick={() => toggleResults(scenario.scenarioId)}
                          />
                          ) : (
                          <Badge
                            icon={getBadgeIcon(runStatus)}
                            iconColor={getIconColor(runStatus)}
                            aria-description="Status of the latest run"
                            variant={getBadgeColor(runStatus)}
                            label={getStatusLabel(runStatus)}
                          />
                          )}
                        </Box>
                      )}
                    </Box>
                  </Box>

                  {/* Results Section - controlled by chevron button */}
                  {latestRun &&
                    !isRunning &&
                    latestRun.trials.length > 0 &&
                    latestRun.trials.some(trial => trial.status === 'COMPLETED' || trial.status === 'ERROR') &&
                    expandedResults.has(scenario.scenarioId) && (
                      <Box paddingLeft="$28" mt="$8">
                        <Box display="flex" flexDirection="column" gap="$12">
                          {latestRun.trials.map((trial, trialIndex) => {
                            const trialStatus = getTrialOverallStatus(trial);
                            const trialKey = `${scenario.scenarioId}-${trial.trialId}`;
                            const isTrialExpanded = expandedTrials.has(trialKey);
                            const hasEvaluationResults = (trial.status === 'COMPLETED' || trial.status === 'ERROR') && trial.evaluationResults.length > 0;
                            
                            const getTrialStatusIcon = () => {
                              if (trialStatus === 'passed') return IconStatusCompleted;
                              if (trialStatus === 'failed') return IconStatusError;
                              return IconStatusPending;
                            };

                            const getTrialStatusColor = () => {
                              if (trialStatus === 'passed') return 'green80';
                              if (trialStatus === 'failed') return 'red80';
                              return 'yellow80';
                            };
                            
                            return (
                              <Box key={trial.trialId} display="flex" flexDirection="column" gap="$4">
                                {/* Trial Header */}
                                <Box display="flex" alignItems="center" gap="$8">
                                  {React.createElement(getTrialStatusIcon(), { size: 20, color: getTrialStatusColor() })}
                                  <Typography variant="body-small" fontWeight="medium">
                                    Test {trialIndex + 1} results
                                    {trial.status === 'ERROR' && trial.evaluationResults.length === 0 && (
                                      <span> - Error (No Results)</span>
                                    )}
                                  </Typography>
                                  {hasEvaluationResults && (
                                    <Button
                                      variant="ghost"
                                      size="small"
                                      icon={isTrialExpanded ? IconChevronDown : IconChevronRight}
                                      onClick={() => toggleTrialDetails(trialKey)}
                                      aria-label="Toggle trial details"
                                    />
                                  )}
                                  {trial.threadId && (
                                    <Button
                                      variant="ghost"
                                      round
                                      size="small"
                                      icon={IconShare}
                                      onClick={() => handleViewResults({ threadId: trial.threadId! })}
                                      aria-label="Navigate to thread"
                                    />
                                  )}
                                </Box>

                                {/* Individual Evaluation Results */}
                                {isTrialExpanded && (trial.status === 'COMPLETED' || trial.status === 'ERROR') && trial.evaluationResults.length > 0 && (
                                  <Box paddingLeft="$16" display="flex" flexDirection="column" gap="$8">
                                    {trial.evaluationResults.map((result) => {
                                      const evaluationKey = `${trial.trialId}-${result.kind}`;
                                      const isExpanded = expandedEvaluations.has(evaluationKey);
                                      const hasDetails = result.explanation || (result.issues && result.issues.length > 0);
                                      
                                      return (
                                        <Box key={evaluationKey} display="flex" flexDirection="column" gap="$4">
                                          <Box display="flex" alignItems="center" gap="$8">
                                            {React.createElement(getEvaluationResultIcon(result), { size: 16, color: getEvaluationResultColor(result) })}
                                            <Typography variant="body-small" fontWeight="medium">
                                              {getEvaluationResultLabel(result)}
                                            </Typography>
                                            <Button
                                                variant="ghost"
                                                size="small"
                                                icon={isExpanded ? IconChevronDown : IconChevronRight}
                                                onClick={() => toggleEvaluationDetails(evaluationKey)}
                                                disabled={!hasDetails}
                                                aria-label="Toggle evaluation details"
                                              />
                                          </Box>
                                          {isExpanded && hasDetails && (
                                            <Box paddingLeft="$14" display="flex" flexDirection="column" gap="$4">
                                              {result.explanation && (
                                                <Typography variant="body-small" color="content.subtle">
                                                  {result.explanation}
                                                </Typography>
                                              )}
                                              {result.issues && result.issues.length > 0 && (
                                                <Box display="flex" flexDirection="column" gap="$2">
                                                  {result.issues.map((issue) => (
                                                    <Typography variant="body-small" color="content.error">
                                                      • {issue}
                                                    </Typography>
                                                  ))}
                                                </Box>
                                              )}
                                            </Box>
                                          )}
                                        </Box>
                                      );
                                    })}
                                  </Box>
                                )}
                              </Box>
                            );
                          })}
                        </Box>
                      </Box>
                    )}
                </Box>
              );
            })
          )}
        </Box>

        {/* Footer - Fixed at bottom */}
        {evaluations.length > 0 && (
          <Box display="flex" justifyContent="flex-end" alignItems="center" flexShrink="0" paddingTop="$8" gap="$4">
            <Button 
              icon={IconSendSmall}
              variant="primary" 
              disabled={isAnyTestRunning}
              onClick={() => handleRunAll(selectedTrialsForAll)}
            >
              {getRunAllButtonText()}
            </Button>
            <Menu
              trigger={
                <Button 
                  variant="outline"
                  icon={IconDotsHorizontal}
                  round
                  disabled={isAnyTestRunning}
                  aria-label="Run all tests options"
                />
              }
            >
              {selectedTrialsForAll === 4 ? (
                <Menu.Item
                  onClick={() => setSelectedTrialsForAll(1)}
                >
                  Switch to single run
                </Menu.Item>
              ) : (
                <Menu.Item
                  onClick={() => setSelectedTrialsForAll(4)}
                >
                  Switch to 4x runs
                </Menu.Item>
              )}
            </Menu>
          </Box>
        )}

      </Box>
      {deleteTarget && (
        <Dialog open onClose={() => setDeleteTarget(null)}>
          <Dialog.Header>
            <Dialog.Header.Title title="Delete Evaluation" />
          </Dialog.Header>
          <Dialog.Content>
            Are you sure you want to delete &quot;{deleteTarget.name}&quot;? This action cannot be undone.
          </Dialog.Content>
          <Dialog.Actions>
            <Button loading={deleteScenarioMutation.isPending} onClick={handleDeleteConfirm}>
              Delete
            </Button>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
          </Dialog.Actions>
        </Dialog>
      )}
      <CreateEvalDialog
        open={createDialogOpen}
        onClose={() => {
          setCreateDialogOpen(false);
          setSuggestedValues(undefined);
          setIsFetchingSuggestion(false);
        }}
        onSubmit={handleCreateEvaluation}
        isLoading={createScenarioMutation.isPending}
        initialValues={suggestedValues}
        isFetchingSuggestion={isFetchingSuggestion}
      />
    </>
  );
};
