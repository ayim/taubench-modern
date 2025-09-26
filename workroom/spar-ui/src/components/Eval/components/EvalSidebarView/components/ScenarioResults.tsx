import { FC } from 'react';
import { Box, Button, Typography } from '@sema4ai/components';
import {
  IconChevronLeft,
  IconChevronRight,
} from '@sema4ai/icons';
import type { components } from '@sema4ai/agent-server-interface';
import { TrialResults } from './TrialResults';
import type { Trial } from '../types';
import { hasTerminalTrials } from '../utils';

export interface ScenarioResultsProps {
  scenarioId: string;
  configuration: components['schemas']['ScenarioRun']['configuration'];
  trials: Trial[];
  selectedRunIndex: number;
  totalRuns: number;
  isRunning: boolean;
  expandedTrials: Set<string>;
  expandedEvaluations: Set<string>;
  onPreviousRun: () => void;
  onNextRun: () => void;
  onToggleTrialDetails: (trialKey: string) => void;
  onToggleEvaluationDetails: (evaluationKey: string) => void;
  onViewResults: (trial: { threadId: string }) => void;
}

export const ScenarioResults: FC<ScenarioResultsProps> = ({
  scenarioId,
  configuration,
  trials,
  selectedRunIndex,
  totalRuns,
  isRunning,
  expandedTrials,
  expandedEvaluations,
  onPreviousRun,
  onNextRun,
  onToggleTrialDetails,
  onToggleEvaluationDetails,
  onViewResults,
}) => {
  const hasCompletedTrials = hasTerminalTrials(trials);

  if (!hasCompletedTrials) {
    return null;
  }

  return (
    <Box paddingLeft="$28" mt="$8">
      <Box display="flex" alignItems="center" justifyContent="space-between" mb="$8">
        <Box display="flex" flexDirection="column" gap="$4">
          <Typography variant="body-medium" fontWeight="medium">
            Test Run {selectedRunIndex + 1}
          </Typography>
          <Box display="flex" flexDirection="column" gap="$4" paddingLeft="$4" marginTop="$4">
            <Typography variant="body-small">
            • Models: {Array.isArray(configuration?.models) ? configuration.models.join(', ') : String(configuration?.models || 'N/A')}
            </Typography>
            <Typography variant="body-small">
            • Arch: {String(configuration?.architecture_version || 'N/A')}
            </Typography>
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
          </Box>
        )}
      </Box>
      
      <Box display="flex" flexDirection="column" gap="$12">
        {trials.map((trial, trialIndex) => (
          <TrialResults
            key={trial.trial_id}
            scenarioId={scenarioId}
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
