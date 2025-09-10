import { FC, useState } from 'react';
import { Box, Button, Typography, Badge, Progress, Menu, Tooltip } from '@sema4ai/components';
import {
  IconChemicalBottle,
  IconShare,
  IconPlay,
  IconPlus,
  IconDotsHorizontal,
  IconChevronDown,
  IconChevronRight,
  IconSendSmall,
  IconInformation,
} from '@sema4ai/icons';
import { EvaluationItem, Scenario } from './types';
import { getRunStatus, getBadgeIcon, getIconColor, getBadgeColor, getStatusLabel } from './utils';

export interface EvalSidebarViewProps {
  evaluations: EvaluationItem[];
  loading: boolean;
  onRunTest: (scenario: Scenario) => void;
  onRunAll: () => void;
  onDeleteScenario: (scenario: Scenario) => void;
  onViewResults: (scenario: Scenario) => void;
  onAddEvaluation: () => void;
}

export const EvalSidebarView: FC<EvalSidebarViewProps> = ({
  evaluations,
  loading,
  onRunTest,
  onRunAll,
  onDeleteScenario,
  onViewResults,
  onAddEvaluation,
}) => {
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set());

  const toggleResults = (scenarioId: string) => {
    setExpandedResults((prev) => {
      const next = new Set(prev);
      if (next.has(scenarioId)) {
        next.delete(scenarioId);
      } else {
        next.add(scenarioId);
      }
      return next;
    });
  };

  if (loading) {
    return (
      <Box display="flex" flexDirection="column" gap="$16" padding="$16">
        <Box display="flex" alignItems="center" justifyContent="center" height="200px">
          <Progress />
        </Box>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column" gap="$16" padding="$16" height="100%">
      {/* Header */}
      <Box display="flex" flexDirection="column" gap="$8">
        <Box display="flex" alignItems="center" gap="$8">
        <Typography variant="display-small">Evaluations</Typography>
        <Tooltip text="Evaluations are used to test the performance of your agent.">
        <IconInformation size="48" color='content.subtle.light' />
        </Tooltip>
        </Box>
        <Typography variant="body-medium">
          All evaluations run will be shown here. Lorem ipsum dolor sit amet. More sample text here.
        </Typography>
      </Box>

      {/* Scenarios List */}
      <Box display="flex" flexDirection="column" gap="$12" flex="1" overflow="auto">
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
            const runStatus = latestRun && getRunStatus(latestRun.trials);

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
                      onClick={() => onRunTest(scenario)}
                      disabled={isRunning}
                      loading={isRunning}
                      icon={IconPlay}
                    >
                      Run Test
                    </Button>
                    <Box>
                      <Menu
                        trigger={
                          <Button
                            variant="outline"
                            icon={IconDotsHorizontal}
                            round
                            aria-label="Scenario actions"
                          />
                        }
                        >
                          <Menu.Item disabled>Edit (Coming Soon)</Menu.Item>
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
                        {latestRun && (
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
                    <Box onClick={() => onViewResults(scenario)}>
                      <Button
                        variant="ghost"
                        round
                        size="small"
                        icon={IconShare}
                        aria-label="View results"
                      />
                    </Box>
                  </Box>
                </Box>

                {/* Results Section - controlled by chevron button */}
                {latestRun &&
                  latestRun.trials.length > 0 &&
                  expandedResults.has(scenario.scenarioId) && (
                    <Box paddingLeft="$28">
                      <Typography variant="body-small" marginBottom="$8">
                        Results
                      </Typography>
                      <Box display="flex" flexDirection="column" gap="$4">
                        {latestRun.trials.map((trial, index) => (
                          <Box key={trial.trialId} display="flex" alignItems="flex-start" gap="$8">
                            {/* Simple dot indicator */}
                            <Box
                              width="8px"
                              height="8px"
                              borderRadius="50%"
                              backgroundColor={trial.status === 'succeeded' ? 'green80' : 'red80'}
                              marginTop="$4"
                              flexShrink="0"
                            />
                            <Box display="flex" flexDirection="column" gap="$2">
                              <Typography variant="body-small">
                                Trial {index + 1} - Overall Result
                              </Typography>
                              {trial.errorMessage && (
                                <Typography variant="body-small" color="content.error">
                                  {trial.errorMessage}
                                </Typography>
                              )}
                            </Box>
                          </Box>
                        ))}
                      </Box>
                    </Box>
                  )}
              </Box>
            );
          })
        )}

        <Box display="flex" justifyContent="flex-start" paddingTop="$8">
          <Button variant="outline" round onClick={onAddEvaluation}>
            <IconPlus size="16" />
            Add Evaluation
          </Button>
        </Box>
      </Box>

      {evaluations.length > 0 && (
        <Box display="flex" justifyContent="flex-end">
          <Button iconAfter={IconSendSmall} variant="primary" onClick={onRunAll}>
            Run All
          </Button>
        </Box>
      )}
    </Box>
  );
};
