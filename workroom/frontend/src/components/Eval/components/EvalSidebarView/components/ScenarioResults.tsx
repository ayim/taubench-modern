import { FC, useMemo } from 'react';
import { Box, Button, Typography, Menu, Badge } from '@sema4ai/components';
import {
  IconChevronLeft,
  IconChevronRight,
  IconMenu,
  IconStatusCompleted,
  IconStatusError,
  IconLoading,
  IconClock,
} from '@sema4ai/icons';
import type { components } from '@sema4ai/agent-server-interface';
import { TrialResults } from './TrialResults';
import type { Trial, ScenarioRun } from '../types';
import { formatDuration, getPassFailCounts, getRunAverageTrialDuration, isRunTerminated } from '../helpers/evalHelpers';
import { isRunThrottled } from '../utils';

// versions in Studio are managed by Studio based on the arch name
// here we repropose what Studio does as a temporary fix
// we should store this info in the agent platform,
// but currently it is not possible
const getArchitectureLabel = (
  configuration: components['schemas']['ScenarioRun']['configuration'] | undefined,
): string => {
  const architectureName =
    configuration && typeof configuration.architecture_name === 'string' ? configuration.architecture_name : null;
  const defaultLabel = '2.0';
  const experimentalLabel = '2.1';

  if (architectureName) {
    const normalizedName = architectureName.toLowerCase();
    if (normalizedName.includes('experimental')) {
      return experimentalLabel;
    }
    if (normalizedName.includes('default')) {
      return defaultLabel;
    }
  }

  const architectureVersion =
    configuration && typeof configuration.architecture_version === 'string' ? configuration.architecture_version : null;

  if (architectureVersion) {
    return architectureVersion;
  }

  return 'N/A';
};

export interface ScenarioResultsProps {
  scenarioId: string;
  scenarioRunId: string | undefined;
  configuration: components['schemas']['ScenarioRun']['configuration'];
  trials: Trial[];
  selectedRunIndex: number;
  totalRuns: number;
  allRuns: ScenarioRun[];
  isRunning: boolean;
  expandedTrials: Set<string>;
  expandedEvaluations: Set<string>;
  onPreviousRun: () => void;
  onNextRun: () => void;
  onSelectRun: (runIndex: number) => void;
  onToggleTrialDetails: (trialKey: string) => void;
  onToggleEvaluationDetails: (evaluationKey: string) => void;
  onViewResults: (trial: { threadId: string; scenarioId: string; scenarioRunId: string }) => void;
}

export const ScenarioResults: FC<ScenarioResultsProps> = ({
  scenarioId,
  scenarioRunId,
  configuration,
  trials,
  selectedRunIndex,
  totalRuns,
  allRuns,
  isRunning,
  expandedTrials,
  expandedEvaluations,
  onPreviousRun,
  onNextRun,
  onSelectRun,
  onToggleTrialDetails,
  onToggleEvaluationDetails,
  onViewResults,
}) => {
  const hasTrials = trials.length > 0;

  const runTerminated = useMemo(() => isRunTerminated(trials), [trials]);
  const averageDurationMs = useMemo(() => getRunAverageTrialDuration(trials), [trials]);
  const averageDurationLabel = useMemo(
    () => (averageDurationMs !== null ? formatDuration(averageDurationMs) : 'N/A'),
    [averageDurationMs],
  );

  if (!hasTrials) {
    return null;
  }

  const handleSelectRun = (runIndex: number) => {
    onSelectRun(runIndex);
  };

  return (
    <Box paddingLeft="$28" mt="$8">
      <Box display="flex" alignItems="center" justifyContent="space-between" mb="$8">
        <Box display="flex" flexDirection="column" gap="$4">
          <Typography variant="body-medium" fontWeight="medium" style={{ userSelect: 'text' }}>
            Test run {totalRuns - selectedRunIndex}
            {selectedRunIndex === 0 ? ' (Latest)' : ''}
          </Typography>
          <Box display="flex" flexDirection="column" gap="$4" paddingLeft="$4" marginTop="$4">
            <Typography variant="body-small" style={{ userSelect: 'text' }}>
              • Models:{' '}
              {Array.isArray(configuration?.models)
                ? configuration.models.join(', ')
                : String(configuration?.models || 'N/A')}
            </Typography>
            <Typography variant="body-small" style={{ userSelect: 'text' }}>
              • Arch: {getArchitectureLabel(configuration)}
            </Typography>
            {runTerminated && (
              <Typography variant="body-small" style={{ userSelect: 'text' }}>
                • Average duration: {averageDurationLabel}
              </Typography>
            )}
          </Box>
        </Box>
        {totalRuns > 1 && (
          <Box display="flex" alignItems="center" gap="$4">
            <Button
              variant="outline"
              round
              size="small"
              icon={IconChevronLeft}
              onClick={onPreviousRun}
              disabled={selectedRunIndex === 0 || isRunning}
              aria-label="Previous run"
            />
            <Button
              variant="outline"
              round
              size="small"
              icon={IconChevronRight}
              onClick={onNextRun}
              disabled={selectedRunIndex >= totalRuns - 1 || isRunning}
              aria-label="Next run"
            />
            <Menu
              maxHeight={200}
              trigger={
                <Button
                  variant="outline"
                  round
                  size="small"
                  icon={IconMenu}
                  disabled={isRunning}
                  aria-label="Jump to run"
                />
              }
            >
              {allRuns.map((run, index) => {
                const runNumber = totalRuns - index;
                const isSelected = index === selectedRunIndex;
                const isLatest = index === 0;

                const runIsRunning =
                  run.trials?.some((trial) => trial.status === 'PENDING' || trial.status === 'EXECUTING') ?? false;

                const throttled = isRunThrottled(run.trials ?? []);

                let statusBadge = null;
                if (runIsRunning) {
                  statusBadge = (
                    <Box display="flex" alignItems="center" gap="$4">
                      <Badge icon={IconLoading} iconColor="blue80" variant="blue" size="small" label="" />
                      {throttled && (
                        <Badge icon={IconClock} iconColor="yellow80" variant="yellow" size="small" label="" />
                      )}
                    </Box>
                  );
                } else if (run.trials && run.trials.length > 0) {
                  const { passed, failed, canceled } = getPassFailCounts(run.trials);
                  const hasResults = passed > 0 || failed > 0 || canceled > 0;

                  if (hasResults) {
                    if (failed > 0 || canceled > 0) {
                      statusBadge = (
                        <Box display="flex" alignItems="center" gap="$4">
                          <Badge icon={IconStatusError} iconColor="content.error" variant="red" size="small" label="" />
                          {throttled && (
                            <Badge icon={IconClock} iconColor="yellow80" variant="yellow" size="small" label="" />
                          )}
                        </Box>
                      );
                    } else if (passed > 0) {
                      statusBadge = (
                        <Box display="flex" alignItems="center" gap="$4">
                          <Badge
                            icon={IconStatusCompleted}
                            iconColor="content.success"
                            variant="green"
                            size="small"
                            label=""
                          />
                          {throttled && (
                            <Badge icon={IconClock} iconColor="yellow80" variant="yellow" size="small" label="" />
                          )}
                        </Box>
                      );
                    }
                  }
                }

                if (!statusBadge && throttled) {
                  statusBadge = <Badge icon={IconClock} iconColor="yellow80" variant="yellow" size="small" label="" />;
                }

                return (
                  <Menu.Item
                    key={run.scenario_run_id}
                    onClick={() => handleSelectRun(index)}
                    aria-selected={isSelected}
                  >
                    <Box display="flex" alignItems="center" justifyContent="space-between" width="100%">
                      <Typography>
                        Test run {runNumber}
                        {isLatest ? ' (Latest)' : ''}
                      </Typography>
                      {statusBadge}
                    </Box>
                  </Menu.Item>
                );
              })}
            </Menu>
          </Box>
        )}
      </Box>

      <Box display="flex" flexDirection="column" gap="$12">
        {trials.map((trial, trialIndex) => (
          <TrialResults
            key={trial.trial_id}
            scenarioId={scenarioId}
            scenarioRunId={scenarioRunId}
            trial={trial}
            trialIndex={trialIndex}
            expandedTrials={expandedTrials}
            expandedEvaluations={expandedEvaluations}
            onToggleTrialDetails={onToggleTrialDetails}
            onToggleEvaluationDetails={onToggleEvaluationDetails}
            onViewResults={onViewResults}
          />
        ))}
      </Box>
    </Box>
  );
};
