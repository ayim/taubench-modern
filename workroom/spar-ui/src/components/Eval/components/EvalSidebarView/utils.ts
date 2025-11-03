import { Color } from '@sema4ai/theme';
import { BadgeVariant } from '@sema4ai/components';
import { IconStatusCompleted, IconStatusError, IconStatusPending, IconLoading } from '@sema4ai/icons';
import { Trial, EvaluationResult } from './types';

export const getIconColor = (status: Trial['status']): Color => {
  switch (status) {
    case 'COMPLETED':
      return 'content.success';
    case 'ERROR':
      return 'content.error';
    case 'EXECUTING':
    case 'PENDING':
      return 'yellow80';
    case 'CANCELED':
    default:
      return 'content.error';
  }
};

export const getBadgeColor = (status: Trial['status']): BadgeVariant => {
  switch (status) {
    case 'COMPLETED':
      return 'green';
    case 'ERROR':
      return 'red';
    case 'EXECUTING':
    case 'PENDING':
      return 'yellow';
    case 'CANCELED':
    default:
      return 'red';
  }
};

export const getBadgeIcon = (status: Trial['status']) => {
  switch (status) {
    case 'COMPLETED':
      return IconStatusCompleted;
    case 'ERROR':
      return IconStatusError;
    case 'EXECUTING':
      return IconLoading;
    case 'PENDING':
    case 'CANCELED':
      return IconStatusPending;
    default:
      return IconStatusPending;
  }
};

export const getStatusLabel = (status: Trial['status']) => {
  switch (status) {
    case 'COMPLETED':
      return 'Passed';
    case 'ERROR':
      return 'Failed';
    case 'EXECUTING':
      return 'Running';
    case 'PENDING':
    case 'CANCELED':
    default:
      return 'Pending';
  }
};

export const getRunStatus = (trials: Trial[]): Trial['status'] => {
  if (trials.length === 0) return 'PENDING';

  if (trials.some((trial) => trial.status === 'EXECUTING')) return 'EXECUTING';

  if (trials.some((trial) => trial.status === 'PENDING')) return 'PENDING';

  if (trials.every((trial) => trial.status === 'COMPLETED')) return 'COMPLETED';

  return 'ERROR';
};

export const getEvaluationResultIcon = (result: EvaluationResult) => {
  return result.passed ? IconStatusCompleted : IconStatusError;
};

export const getEvaluationResultColor = (result: EvaluationResult): Color => {
  return result.passed ? 'content.success' : 'content.error';
};

export const getEvaluationResultBadgeColor = (result: EvaluationResult): BadgeVariant => {
  return result.passed ? 'green' : 'red';
};

export const getEvaluationResultLabel = (result: EvaluationResult): string => {
  switch (result.kind) {
    case 'response_accuracy':
      return 'Response Accuracy';
    case 'flow_adherence':
      return 'Flow Adherence';
    case 'action_calling':
      return 'Action Calling';
    default:
      return 'Unknown';
  }
};

export const isTrialTerminal = (trial: Trial): boolean => {
  return trial.status === 'COMPLETED' || trial.status === 'ERROR' || trial.status === 'CANCELED';
};

export const hasTerminalTrials = (trials: Trial[]): boolean => {
  return trials.some(isTrialTerminal);
};
