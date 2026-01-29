import { FC } from 'react';
import { Box, Typography, Banner, Button, Menu, Tooltip } from '@sema4ai/components';
import {
  IconLightBulb,
  IconSendSmall,
  IconDotsHorizontal,
  IconClose,
  IconQuestionMarkCircle,
  IconCloseCircle,
  IconAlertCircle,
} from '@sema4ai/icons';
import type { BatchSummary } from '../types';

export interface UserFacingMetricsProps {
  batchSummary: BatchSummary | null;
  showRunbookWarning: boolean;
  onDismissRunbookWarning: () => void;
  onRunAllTests: (numTrials: number) => void;
  selectedTrialsForAll: number;
  onSetSelectedTrialsForAll: (numTrials: number) => void;
  isAnyTestRunning: boolean;
  isBatchRunning: boolean;
  isCancelingAll: boolean;
  onCancelAllTests: () => void;
  hasEvaluations: boolean;
}

export const UserFacingMetrics: FC<UserFacingMetricsProps> = ({
  batchSummary,
  showRunbookWarning,
  onDismissRunbookWarning,
  onRunAllTests,
  selectedTrialsForAll,
  onSetSelectedTrialsForAll,
  isAnyTestRunning,
  isBatchRunning,
  isCancelingAll,
  onCancelAllTests,
  hasEvaluations,
}) => {
  const totalScenarios = batchSummary?.statistics.total_scenarios ?? 0;
  const successfulScenarios = batchSummary?.statistics.completed_scenarios ?? 0;
  const totalTrials = batchSummary?.statistics.total_trials ?? 0;
  const successfulTrials = batchSummary?.statistics.completed_trials ?? 0;
  const failedTrials = batchSummary?.statistics.failed_trials ?? 0;

  const hasCompletedTrials = successfulTrials + failedTrials > 0;
  const hasRunBatch = !!batchSummary && hasCompletedTrials;
  const overallPercent = totalTrials > 0 ? Math.round((successfulTrials / Math.max(totalTrials, 1)) * 100) : 0;

  const allowConsistency = (batchSummary?.numTrials ?? 0) > 1;
  const hasConsistencyData = allowConsistency && totalScenarios > 0;
  const consistencyPercent = hasConsistencyData
    ? Math.round((successfulScenarios / Math.max(totalScenarios, 1)) * 100)
    : 0;

  const overallDetailText =
    batchSummary && totalScenarios > 0 && totalTrials > 0
      ? `${totalScenarios} scenarios evaluated ${batchSummary.numTrials} ${batchSummary.numTrials === 1 ? 'time' : 'times'} each\n${successfulTrials} trials passed`
      : '';

  const consistencyDetailText =
    batchSummary && hasConsistencyData
      ? `${successfulScenarios} scenarios passed all ${batchSummary.numTrials} runs.`
      : '';

  const models = batchSummary?.metadata?.models || [];
  const modelsText = models.length > 0 ? models.join(', ') : null;

  const runbookUpdatedAt = batchSummary?.metadata?.runbook_updated_at;
  const runbookDate = runbookUpdatedAt ? new Date(runbookUpdatedAt) : null;
  const runbookText = runbookDate
    ? `Updated at ${runbookDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}, ${runbookDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
    : null;

  const scenarioIssues = batchSummary?.scenarioIssues ?? {};
  const stalledScenarios = Object.values(scenarioIssues).filter((issue) => issue.stalled > 0);
  const slowScenarios = Object.values(scenarioIssues).filter((issue) => issue.slow > 0 && issue.stalled === 0);
  const isExecutionLocked = isAnyTestRunning || isBatchRunning;

  const runTestsMenu = (
    <Menu
      trigger={
        <Button
          variant="outline"
          round
          icon={IconDotsHorizontal}
          aria-label="Run tests options"
          disabled={isExecutionLocked}
        />
      }
    >
      <Menu.Item onClick={() => onSetSelectedTrialsForAll(1)} disabled={isExecutionLocked}>
        Switch to 1x runs
      </Menu.Item>
      <Menu.Item onClick={() => onSetSelectedTrialsForAll(4)} disabled={isExecutionLocked}>
        Switch to 4x runs
      </Menu.Item>
    </Menu>
  );

  return (
    <Box
      backgroundColor="background.subtle.light"
      borderRadius="$20"
      padding="$16"
      display="flex"
      flexDirection="column"
      gap="$16"
    >
      <Box display="flex" gap="$32">
        <Box display="flex" flexDirection="column" gap="$4">
          <Box display="flex" alignItems="center" gap="$4">
            <Typography variant="body-medium" color="content.subtle.light" style={{ userSelect: 'text' }}>
              Overall Test Result
            </Typography>
            <Tooltip text="The percentage of successful trials out of all trials.">
              <IconQuestionMarkCircle size="48" color="content.subtle.light" />
            </Tooltip>
          </Box>
          <Typography variant="display-small" color="content.primary" style={{ userSelect: 'text' }}>
            {isExecutionLocked || !hasRunBatch ? '--' : `${overallPercent}%`}
          </Typography>
          {!isExecutionLocked && overallDetailText && (
            <Typography
              variant="body-small"
              color="content.success"
              style={{ whiteSpace: 'pre-line', userSelect: 'text' }}
            >
              {overallDetailText}
            </Typography>
          )}
        </Box>

        {hasConsistencyData && (
          <Box display="flex" flexDirection="column" gap="$4">
            <Box display="flex" alignItems="center" gap="$4">
              <Typography variant="body-medium" color="content.subtle.light" style={{ userSelect: 'text' }}>
                Consistency
              </Typography>
              <Tooltip text="The percentage of successful scenarios out of all scenarios.">
                <IconQuestionMarkCircle size="48" color="content.subtle.light" />
              </Tooltip>
            </Box>
            <Typography variant="display-small" color="content.primary" style={{ userSelect: 'text' }}>
              {isExecutionLocked || !hasRunBatch ? '--' : `${consistencyPercent}%`}
            </Typography>
            {!isExecutionLocked && consistencyDetailText && (
              <Typography variant="body-small" color="content.success" style={{ userSelect: 'text' }}>
                {consistencyDetailText}
              </Typography>
            )}
          </Box>
        )}
      </Box>

      {showRunbookWarning && (
        <Banner
          message=""
          description="Your runbook / agent was updated. Run all tests for accuracy and consistency information."
          icon={IconLightBulb}
          variant="info"
        >
          <Button
            variant="ghost"
            aria-label="Close"
            size="small"
            iconAfter={IconClose}
            onClick={onDismissRunbookWarning}
          />
        </Banner>
      )}

      {!showRunbookWarning &&
        (modelsText || runbookText || stalledScenarios.length > 0 || slowScenarios.length > 0) && (
          <Box display="flex" flexDirection="column" gap="$8">
            {modelsText && (
              <Typography variant="body-small" color="content.primary" style={{ userSelect: 'text' }}>
                • Model: {modelsText}
              </Typography>
            )}
            {runbookText && (
              <Typography variant="body-small" color="content.primary" style={{ userSelect: 'text' }}>
                • Runbook: {runbookText}
              </Typography>
            )}
            {stalledScenarios.length > 0 && (
              <Box display="flex" alignItems="center" gap="$2">
                <IconAlertCircle size={14} color="content.error" />
                <Typography variant="body-small" color="content.error" style={{ userSelect: 'text' }}>
                  {stalledScenarios.length === 1
                    ? `Scenario ${stalledScenarios[0].name} has ${stalledScenarios[0].stalled} stalled ${
                        stalledScenarios[0].stalled === 1 ? 'run' : 'runs'
                      }`
                    : `${stalledScenarios.length} scenarios have stalled runs`}
                </Typography>
              </Box>
            )}
            {slowScenarios.length > 0 && (
              <Box display="flex" alignItems="center" gap="$2">
                <IconQuestionMarkCircle size={14} />
                <Typography variant="body-small" style={{ userSelect: 'text' }}>
                  {slowScenarios.length === 1
                    ? `Scenario ${slowScenarios[0].name} has ${slowScenarios[0].slow} slow ${
                        slowScenarios[0].slow === 1 ? 'run' : 'runs'
                      }`
                    : `${slowScenarios.length} scenarios have slow runs`}
                </Typography>
              </Box>
            )}
          </Box>
        )}

      {/* Run All Tests Button - Bottom Row */}
      {hasEvaluations && (
        <Box display="flex" alignItems="center" gap="$8" justifyContent="flex-end">
          <Button
            icon={IconSendSmall}
            variant="outline"
            round
            disabled={isExecutionLocked}
            onClick={() => onRunAllTests(selectedTrialsForAll)}
          >
            {selectedTrialsForAll === 1 ? 'Run All Tests' : `Run All Tests (${selectedTrialsForAll}x)`}
          </Button>
          {isBatchRunning && (
            <Button icon={IconCloseCircle} variant="outline" round onClick={onCancelAllTests} loading={isCancelingAll}>
              Cancel All
            </Button>
          )}
          {runTestsMenu}
        </Box>
      )}
    </Box>
  );
};
