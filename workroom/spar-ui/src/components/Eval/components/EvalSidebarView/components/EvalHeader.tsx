import { FC, useMemo } from 'react';
import { Box, Button, Typography, Tooltip, Divider, Menu } from '@sema4ai/components';
import {
  IconInformation,
  IconPlus,
  IconLightBulb,
  IconDownload,
  IconUpload,
  IconDotsHorizontal,
  IconSendSmall,
  IconStatusEnabled,
  IconLoading,
} from '@sema4ai/icons';
import type { BatchSummary } from '../types';

export interface EvalHeaderProps {
  hasMessages: boolean;
  hasEvaluations: boolean;
  onAddEvaluation: () => void;
  isFetchingSuggestion: boolean;
  onExportScenarios: () => void;
  isExporting: boolean;
  onImportScenarios: () => void;
  isImporting: boolean;
  onRunAll: (numTrials: number) => void;
  onSetSelectedTrialsForAll: (numTrials: number) => void;
  selectedTrialsForAll: number;
  isAnyTestRunning: boolean;
  onCancelAll: () => void;
  isCancelingAll: boolean;
  batchSummary: BatchSummary | null;
  isBatchSummaryOutdated: boolean;
}

export const EvalHeader: FC<EvalHeaderProps> = ({
  hasMessages,
  hasEvaluations,
  onAddEvaluation,
  isFetchingSuggestion,
  onExportScenarios,
  isExporting,
  onImportScenarios,
  isImporting,
  onRunAll,
  onSetSelectedTrialsForAll,
  selectedTrialsForAll,
  isAnyTestRunning,
  onCancelAll,
  isCancelingAll,
  batchSummary,
  isBatchSummaryOutdated,
}) => {
  const { hasSummary, overallPercentDisplay, overallDetailText } = useMemo(() => {
    if (!batchSummary) {
      return {
        hasSummary: false,
        overallPercentDisplay: '--',
        overallDetailText: 'TBD',
      };
    }

    const totalScenarios = batchSummary.statistics.total_scenarios ?? 0;
    const successfulScenarios = batchSummary.statistics.completed_scenarios ?? 0;
    const totalTrials = batchSummary.statistics.total_trials ?? 0;
    const successfulTrials = batchSummary.statistics.completed_trials ?? 0;

    const overallPercent = totalTrials > 0 ? Math.round((successfulTrials / Math.max(totalTrials, 1)) * 100) : 0;

    const allowConsistency = batchSummary.numTrials > 1;
    const hasConsistencyData = allowConsistency && totalScenarios > 0;

    return {
      hasSummary: true,
      overallPercentDisplay: `${overallPercent}%`,
      overallDetailText: hasConsistencyData
        ? `${successfulScenarios} of ${totalScenarios} scenarios passed all trials`
        : '',
    };
  }, [batchSummary]);
  const evaluationActionsMenu = (
    <Menu
      trigger={
        <Button variant="outline" round size="small" icon={IconDotsHorizontal} aria-label="Evaluation actions" />
      }
    >
      {hasEvaluations && (
        <Menu.Item
          icon={IconInformation}
          onClick={() => onSetSelectedTrialsForAll(selectedTrialsForAll === 4 ? 1 : 4)}
          disabled={isAnyTestRunning}
        >
          {selectedTrialsForAll === 4 ? 'Switch to 1x' : 'Switch to 4x runs'}
        </Menu.Item>
      )}
      <Menu.Item icon={IconUpload} onClick={onImportScenarios} disabled={isImporting}>
        {isImporting ? 'Importing...' : 'Import Evaluations'}
      </Menu.Item>
      <Menu.Item icon={IconDownload} onClick={onExportScenarios} disabled={!hasEvaluations || isExporting}>
        {isExporting ? 'Exporting...' : 'Export Evaluations'}
      </Menu.Item>
    </Menu>
  );

  return (
    <Box display="flex" flexDirection="column" gap="$8" flexShrink="0">
      <Box display="flex" alignItems="center" gap="$8">
        <Typography variant="display-small">Evaluations</Typography>
        <Tooltip text="Evaluations are used to test the performance of your agent.">
          <IconInformation size="48" color="content.subtle.light" />
        </Tooltip>
      </Box>

      <Typography variant="body-medium">All evaluation runs will be shown here.</Typography>

      <Box
        display="flex"
        justifyContent={hasMessages ? 'flex-start' : 'space-between'}
        alignItems="center"
        paddingTop="$8"
        mb="$8"
        gap="$12"
        flexWrap="wrap"
      >
        {!hasMessages && (
          <Box
            backgroundColor="background.notification.light"
            padding="$20"
            borderRadius="$12"
            display="flex"
            alignItems="center"
            gap="$8"
          >
            <IconLightBulb size={24} />
            <Typography variant="body-medium">Talk to your agent to be able to add an evaluation.</Typography>
          </Box>
        )}

        <Box display="flex" alignItems="center" gap="$8">
          {hasMessages && (
            <Button
              variant="outline"
              round
              onClick={onAddEvaluation}
              loading={isFetchingSuggestion}
              disabled={isFetchingSuggestion}
            >
              {!isFetchingSuggestion && (
                <>
                  <IconPlus size="16" />
                  Add Evaluation
                </>
              )}
              {isFetchingSuggestion && 'Generating Evaluation...'}
            </Button>
          )}

          {hasEvaluations && (
            <Box display="flex" flexDirection="row" gap="$4" flexWrap="wrap" alignItems="center">
              <Button
                icon={IconSendSmall}
                variant="primary"
                disabled={isAnyTestRunning}
                onClick={() => onRunAll(selectedTrialsForAll)}
              >
                {selectedTrialsForAll === 1 ? 'Run All Tests' : `Run All Tests (${selectedTrialsForAll}x)`}
              </Button>
              {isAnyTestRunning && (
                <Button variant="secondary" onClick={onCancelAll} disabled={isCancelingAll} loading={isCancelingAll}>
                  Cancel All
                </Button>
              )}
            </Box>
          )}

          {evaluationActionsMenu}
        </Box>
      </Box>
      {hasSummary && (
        <Box display="flex" flexDirection="column" gap="$4">
          <Box>
            <Typography variant="body-medium" color="content.subtle.light">
              Overall Test Results
            </Typography>
            <Box display="flex" alignItems="center" gap="$4">
              <Typography variant="display-small" color="content.primary">
                {overallPercentDisplay}
              </Typography>
              {isAnyTestRunning ? (
                <IconLoading size={20} color="yellow80" aria-label="Overall test results running indicator" />
              ) : (
                <IconStatusEnabled size={16} color="content.success" aria-label="Overall test results pass indicator" />
              )}
            </Box>
            {!isAnyTestRunning && overallDetailText && (
              <Typography variant="body-small" color="content.success">
                {overallDetailText}
              </Typography>
            )}
          </Box>

          {isBatchSummaryOutdated && (
            <Typography variant="body-small" color="background.error">
              Individual scenario runs were executed after this batch; results may be outdated.
            </Typography>
          )}
        </Box>
      )}

      <Divider />
    </Box>
  );
};
