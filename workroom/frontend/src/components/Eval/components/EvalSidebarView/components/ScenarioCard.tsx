import React, { FC } from 'react';
import { Box, Button, Typography, Badge, Menu, Tooltip } from '@sema4ai/components';
import {
  IconChemicalBottle,
  IconPlay,
  IconDotsHorizontal,
  IconChevronDown,
  IconChevronUp,
  IconInformation,
  IconStatusCompleted,
  IconStatusError,
  IconStatusPending,
  IconLoading,
  IconTrash,
  IconCloseCircle,
  IconArrowRightCircle,
  IconEdit,
  IconClock,
  IconAlertCircle,
} from '@sema4ai/icons';
import { formatShortDateTime } from '~/components/helpers';
import { getRunStatus, hasTerminalTrials, isRunThrottled } from '../utils';
import { getPassFailCounts, getLatestTrialProgressSummary } from '../helpers/evalHelpers';
import type { Scenario, ScenarioRun, Trial } from '../types';

export interface ScenarioCardProps {
  scenario: Scenario;
  currentRun: ScenarioRun | null;
  isRunning: boolean;
  isAnyTestRunning: boolean;
  isBatchRunning: boolean;
  selectedTrials: number;
  expandedResults: boolean;
  onRunTest: (numTrials: number) => void;
  onToggleResults: () => void;
  onDeleteScenario: () => void;
  onEditScenario: () => void;
  onSetSelectedTrials: (numTrials: number) => void;
  onCancelTest: () => void;
  children?: React.ReactNode;
}

export const ScenarioCard: FC<ScenarioCardProps> = ({
  scenario,
  currentRun,
  isRunning,
  isAnyTestRunning,
  isBatchRunning,
  selectedTrials,
  expandedResults,
  onRunTest,
  onToggleResults,
  onDeleteScenario,
  onEditScenario,
  onSetSelectedTrials,
  onCancelTest,
  children,
}) => {
  const runStatus = isRunning ? 'EXECUTING' : currentRun?.trials && getRunStatus(currentRun.trials);
  const trials = currentRun?.trials ?? [];
  const progressSummary = trials.length > 0 ? getLatestTrialProgressSummary(trials) : null;
  const stalledTrials = trials.filter((trial: Trial) => trial.progress_classification === 'stalled');
  const slowTrials = trials.filter((trial: Trial) => trial.progress_classification === 'slow');

  const formatTrialLabel = (trial: Trial): string => `Trial #${trial.index_in_run + 1}`;

  const summarizeWarnings = (warningTrials: Trial[]): string | null => {
    if (warningTrials.length === 0) {
      return null;
    }
    const label = formatTrialLabel(warningTrials[0]);
    if (warningTrials.length === 1) {
      return label;
    }
    return `${label} and ${warningTrials.length - 1} more`;
  };

  const stalledWarning = summarizeWarnings(stalledTrials);
  const slowWarning = summarizeWarnings(slowTrials);

  const handleResultsToggle = () => {
    onToggleResults();
  };

  const renderStatusBadges = () => {
    if (!currentRun) {
      return null;
    }

    const throttleBadge = isRunThrottled(currentRun.trials ?? []) ? (
      <Badge icon={IconClock} iconColor="yellow80" variant="yellow" size="small" label="Throttled" />
    ) : null;

    if (isRunning) {
      return (
        <Box display="flex" alignItems="center" gap="$4">
          <Badge icon={IconLoading} iconColor="yellow80" variant="yellow" label="Running" />
          {throttleBadge}
        </Box>
      );
    }

    const hasCompletedTrials = hasTerminalTrials(currentRun.trials ?? []);

    if (hasCompletedTrials) {
      const { passed, failed, canceled } = getPassFailCounts(currentRun.trials ?? []);

      return (
        <Box display="flex" alignItems="center" gap="$4">
          <Badge
            variant="secondary"
            icon={IconArrowRightCircle}
            forwardedAs="button"
            label="Results"
            iconVisible
            iconAfter={expandedResults ? IconChevronUp : IconChevronDown}
            onClick={handleResultsToggle}
          />
          {passed > 0 && (
            <Badge
              variant="green"
              icon={IconStatusCompleted}
              iconColor="green80"
              label={passed.toString()}
              size="small"
            />
          )}
          {failed > 0 && (
            <Badge variant="red" icon={IconStatusError} iconColor="red80" label={failed.toString()} size="small" />
          )}
          {canceled > 0 && (
            <Badge
              variant="yellow"
              icon={IconStatusPending}
              iconColor="yellow80"
              label={canceled.toString()}
              size="small"
            />
          )}
          {throttleBadge}
        </Box>
      );
    }

    return throttleBadge;
  };

  return (
    <Box display="flex" flexDirection="column" gap="$8" mt="$16">
      <Box display="flex" flexDirection="column" gap="$8">
        <Box>
          <Box display="flex" alignItems="center" gap="$8" flexDirection="row" justifyContent="space-between">
            <Box display="flex" alignItems="center" gap="$8">
              <IconChemicalBottle size={20} />
              <Typography variant="display-headline" style={{ userSelect: 'text' }}>
                {scenario.name}
              </Typography>
            </Box>

            <Menu
              trigger={
                <Button
                  variant="outline"
                  icon={IconDotsHorizontal}
                  round
                  aria-label="Scenario actions"
                  disabled={isAnyTestRunning}
                  size="small"
                />
              }
            >
              {selectedTrials === 4 ? (
                <Tooltip text='Run tests 1 time when clicking "Run Test"'>
                  <Menu.Item onClick={() => onSetSelectedTrials(1)} icon={IconInformation}>
                    Switch to 1x
                  </Menu.Item>
                </Tooltip>
              ) : (
                <Tooltip text='Run tests 4 times when clicking "Run Test"'>
                  <Menu.Item onClick={() => onSetSelectedTrials(4)} icon={IconInformation}>
                    Switch to 4x
                  </Menu.Item>
                </Tooltip>
              )}
              <Menu.Item icon={IconEdit} onClick={onEditScenario}>
                Edit evaluation
              </Menu.Item>
              <Menu.Item icon={IconTrash} onClick={onDeleteScenario}>
                Delete
              </Menu.Item>
            </Menu>
          </Box>

          <Typography variant="body-small" mt="$8" style={{ userSelect: 'text' }}>
            {scenario.description}
          </Typography>
        </Box>

        <Box width="100%" display="flex" alignItems="center" gap="$8">
          {isRunning ? (
            <Button variant="outline" round icon={IconCloseCircle} onClick={onCancelTest}>
              Cancel
            </Button>
          ) : (
            <Button
              variant="outline"
              round
              disabled={isBatchRunning}
              icon={IconPlay}
              onClick={() => onRunTest(selectedTrials)}
            >
              {selectedTrials === 1 ? 'Run Test' : `Run Test (${selectedTrials}x)`}
            </Button>
          )}

          {runStatus && (
            <Box display="flex" alignItems="center" gap="$4">
              {renderStatusBadges()}
            </Box>
          )}
        </Box>

        {progressSummary && progressSummary.lastProgressAt && (
          <Box display="flex" alignItems="center" gap="$2" color="content.subtle">
            <IconClock size={14} />
            <Typography variant="body-small" color="content.subtle" style={{ userSelect: 'text' }}>
              Latest update {formatShortDateTime(progressSummary.lastProgressAt)} from trial #
              {progressSummary.trialIndex + 1}
              {progressSummary.currentPhase ? ` • Phase ${progressSummary.currentPhase}` : ''}
            </Typography>
          </Box>
        )}

        {stalledWarning && (
          <Box display="flex" alignItems="center" gap="$2">
            <IconAlertCircle size={14} />
            <Typography variant="body-small" color="content.error" style={{ userSelect: 'text' }}>
              Warning: {stalledWarning} {stalledTrials.length > 1 ? 'are' : 'is'} stalled
            </Typography>
          </Box>
        )}

        {slowWarning && (
          <Box display="flex" alignItems="center" gap="$2">
            <IconInformation size={14} />
            <Typography variant="body-small" style={{ userSelect: 'text' }}>
              Heads up: {slowWarning} {slowTrials.length > 1 ? 'are' : 'is'} running slowly
            </Typography>
          </Box>
        )}
      </Box>

      {children}
    </Box>
  );
};
