import React, { FC, useState } from 'react';
import { Box, Button, Typography, Badge, Progress, Menu, Tooltip, Divider } from '@sema4ai/components';
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
} from '@sema4ai/icons';
import { useThreadMessagesQuery } from '../../../../queries';
import { useParams } from '../../../../hooks';
import { EvaluationItem, Scenario } from './types';
import { getRunStatus, getBadgeIcon, getIconColor, getBadgeColor, getStatusLabel, getEvaluationResultColor, getEvaluationResultLabel, getTrialOverallStatus, getEvaluationResultIcon } from './utils';

export interface EvalSidebarViewProps {
  evaluations: EvaluationItem[];
  loading: boolean;
  onRunTest: (scenario: Scenario, numTrials: number) => void;
  onRunAll: (numTrials: number) => void;
  onDeleteScenario: (scenario: Scenario) => void;
  onViewResults: (trial: { threadId: string }) => void;
  onDownloadScenario: (scenario: Scenario) => void;
  onAddEvaluation: () => void;
}

export const EvalSidebarView: FC<EvalSidebarViewProps> = ({
  evaluations,
  loading,
  onRunTest,
  onRunAll,
  onDeleteScenario,
  onViewResults,
  onDownloadScenario,
  onAddEvaluation,
}) => {
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set());
  const [expandedTrials, setExpandedTrials] = useState<Set<string>>(new Set());
  const [expandedEvaluations, setExpandedEvaluations] = useState<Set<string>>(new Set());
  const [selectedTrials, setSelectedTrials] = useState<Map<string, number>>(new Map()); // scenarioId -> numTrials
  const [selectedTrialsForAll, setSelectedTrialsForAll] = useState<number>(1);
  
  const isAnyTestRunning = evaluations.some(evaluation => evaluation.isRunning);

  const { threadId } = useParams('/thread/$agentId/$threadId');
  const { data: messages = [] } = useThreadMessagesQuery({
    threadId,
  });

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
                    <Box display="flex" alignItems="center">
                      <Button
                        variant="outline"
                        round
                        disabled={isRunning || isAnyTestRunning}
                        loading={isRunning}
                        icon={IconPlay}
                        onClick={() => onRunTest(scenario, getSelectedTrialsForScenario(scenario.scenarioId))}
                      >
                        {getRunTestButtonText(scenario.scenarioId)}
                      </Button>
                      <Menu
                        trigger={
                          <Button
                            variant="ghost"
                            size="small"
                            disabled={isRunning || isAnyTestRunning}
                            icon={IconChevronDown}
                            aria-label="Select number of trials"
                          />
                        }
                      >
                        <Menu.Item
                          onClick={() => {
                            setSelectedTrials(prev => new Map(prev).set(scenario.scenarioId, 1));
                          }}
                        >
                          Run Test 1x
                        </Menu.Item>
                        <Menu.Item
                          onClick={() => {
                            setSelectedTrials(prev => new Map(prev).set(scenario.scenarioId, 4));
                          }}
                        >
                          Run Test 4x
                        </Menu.Item>
                      </Menu>
                    </Box>
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
                          <Menu.Item 
                            icon={IconDownload}
                            onClick={() => onDownloadScenario(scenario)}
                          >
                            Download JSON
                          </Menu.Item>
                          <Menu.Item onClick={() => onDeleteScenario(scenario)}>Delete</Menu.Item>
                        </Menu>
                    </Box>
                    {runStatus && (
                      <Box display="flex" alignItems="center" gap="$4">
                        <Badge
                          icon={getBadgeIcon(runStatus)}
                          iconColor={getIconColor(runStatus)}
                          aria-description="Status of the latest run"
                          variant={getBadgeColor(runStatus)}
                          label={getStatusLabel(runStatus)}
                        />
                        {latestRun && !isRunning && latestRun.trials.some(trial => trial.status === 'COMPLETED' || trial.status === 'ERROR') && (
                          <Button
                            variant="ghost"
                            size="small"
                            icon={expandedResults.has(scenario.scenarioId) ? IconChevronDown : IconChevronRight}
                            onClick={() => toggleResults(scenario.scenarioId)}
                            aria-label="Toggle results"
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
                    <Box paddingLeft="$28">
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
                                  Trial {trialIndex + 1}
                                  {(trial.status === 'COMPLETED' || trial.status === 'ERROR') && trial.evaluationResults.length > 0 && (
                                    <span> - {trialStatus === 'passed' ? 'All Tests Passed' : 'Some Tests Failed'}</span>
                                  )}
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
                                    onClick={() => onViewResults({ threadId: trial.threadId! })}
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
                                            {getEvaluationResultLabel(result)}: {result.passed ? 'Passed' : 'Failed'}
                                          </Typography>
                                          {hasDetails && (
                                            <Button
                                              variant="ghost"
                                              size="small"
                                              icon={isExpanded ? IconChevronDown : IconChevronRight}
                                              onClick={() => toggleEvaluationDetails(evaluationKey)}
                                              aria-label="Toggle evaluation details"
                                            />
                                          )}
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

        <Divider />

        <Box display="flex" justifyContent="flex-start" paddingTop="$8">
          {messages.length === 0 ? (
            <Box backgroundColor="yellow20" padding="$20" borderRadius="$12" display="flex" alignItems="center" gap="$8">
            <IconLightBulb size={24} />
            <Typography variant="body-medium">
              You must have at least one message in the thread to add an evaluation.
            </Typography>
            </Box>
          ) : (
            <Button variant="outline" round onClick={onAddEvaluation} disabled={messages.length === 0}>
            <IconPlus size="16" />
            Add Evaluation
          </Button>
          )}
        </Box>
      </Box>

      {/* Footer - Fixed at bottom */}
      {evaluations.length > 0 && (
        <Box display="flex" justifyContent="flex-end" alignItems="center" flexShrink="0" paddingTop="$8" gap="$4">
          <Button 
            icon={IconSendSmall}
            variant="primary" 
            disabled={isAnyTestRunning}
            onClick={() => onRunAll(selectedTrialsForAll)}
          >
            {getRunAllButtonText()}
          </Button>
          <Menu
            trigger={
              <Button 
                variant="ghost"
                size="small"
                disabled={isAnyTestRunning}
                icon={IconChevronDown}
                aria-label="Select number of trials for all tests"
              />
            }
          >
            <Menu.Item
              onClick={() => setSelectedTrialsForAll(1)}
            >
              Run All Tests 1x
            </Menu.Item>
            <Menu.Item
              onClick={() => setSelectedTrialsForAll(4)}
            >
              Run All Tests 4x
            </Menu.Item>
          </Menu>
        </Box>
      )}

    </Box>
  );
};
