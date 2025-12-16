import type { Trial } from '../types';

const TERMINAL_STATUSES: ReadonlySet<Trial['status']> = new Set(['COMPLETED', 'ERROR', 'CANCELED']);

const parseTimestamp = (value: string | undefined | null): number | null => {
  if (!value) {
    return null;
  }

  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : timestamp;
};

const trialDurationMs = (trial: Trial): number | null => {
  const startedAt = parseTimestamp(trial.execution_state?.started_at) ?? parseTimestamp(trial.created_at);
  const finishedAt =
    parseTimestamp(trial.execution_state?.finished_at) ??
    parseTimestamp(trial.status_updated_at) ??
    parseTimestamp(trial.updated_at);

  if (startedAt === null || finishedAt === null || finishedAt < startedAt) {
    return null;
  }

  return finishedAt - startedAt;
};

export const getPassFailCounts = (
  trials: Trial[],
): {
  passed: number;
  failed: number;
  canceled: number;
} => {
  let passed = 0;
  let failed = 0;
  let canceled = 0;

  trials.forEach((trial) => {
    if (trial.status === 'CANCELED') {
      canceled += 1;
    } else if (trial.status === 'ERROR') {
      failed += 1;
    } else if (trial.status === 'COMPLETED') {
      const hasEvaluationResults = trial.evaluation_results && trial.evaluation_results.length > 0;
      if (hasEvaluationResults && trial.evaluation_results?.every((result) => result.passed)) {
        passed += 1;
      } else {
        failed += 1;
      }
    }
    // Skip PENDING/EXECUTING trials as they don't count towards final results
  });

  return { passed, failed, canceled };
};

export const isRunTerminated = (trials: Trial[]): boolean => {
  if (trials.length === 0) {
    return false;
  }

  return trials.every((trial) => TERMINAL_STATUSES.has(trial.status));
};

export const getRunAverageTrialDuration = (trials: Trial[]): number | null => {
  const durations = trials.map(trialDurationMs).filter((duration): duration is number => duration !== null);

  if (durations.length === 0) {
    return null;
  }

  const totalDuration = durations.reduce((total, current) => total + current, 0);
  return totalDuration / durations.length;
};

export interface TrialProgressSummary {
  trialId: string;
  trialIndex: number;
  lastProgressAt: string;
  currentPhase: string | null;
  status: Trial['status'];
}

export const getLatestTrialProgressSummary = (trials: Trial[]): TrialProgressSummary | null => {
  if (!trials || trials.length === 0) {
    return null;
  }

  let latest: TrialProgressSummary | null = null;
  let latestTimestamp: number | null = null;

  const pickTimestamp = (trial: Trial): { timestamp: number; value: string } | null => {
    const candidateValues: (string | undefined | null)[] = [
      trial.execution_state?.last_progress_at,
      trial.execution_state?.finished_at,
      trial.status_updated_at,
      trial.updated_at,
    ];

    for (let idx = 0; idx < candidateValues.length; idx += 1) {
      const candidate = candidateValues[idx];
      const parsed = parseTimestamp(candidate);
      if (parsed !== null) {
        return { timestamp: parsed, value: candidate ?? new Date(parsed).toISOString() };
      }
    }

    return null;
  };

  trials.forEach((trial) => {
    const picked = pickTimestamp(trial);
    if (!picked) {
      return;
    }

    if (latestTimestamp === null || picked.timestamp > latestTimestamp) {
      latestTimestamp = picked.timestamp;
      latest = {
        trialId: trial.trial_id,
        trialIndex: trial.index_in_run,
        lastProgressAt: picked.value,
        currentPhase: trial.execution_state?.current_phase ?? null,
        status: trial.status,
      };
    }
  });

  return latest;
};

export interface TrialStatusBreakdown {
  throttled: number;
  running: number;
  pending: number;
  completed: number;
  failed: number;
  canceled: number;
}

export const getTrialStatusBreakdown = (trials: Trial[]): TrialStatusBreakdown => {
  return trials.reduce<TrialStatusBreakdown>(
    (acc, trial) => {
      if (trial.retry_after_at) {
        acc.throttled += 1;
      }

      switch (trial.status) {
        case 'EXECUTING':
          acc.running += 1;
          break;
        case 'PENDING':
          acc.pending += 1;
          break;
        case 'COMPLETED':
          acc.completed += 1;
          break;
        case 'ERROR':
          acc.failed += 1;
          break;
        case 'CANCELED':
          acc.canceled += 1;
          break;
        default:
          break;
      }

      return acc;
    },
    { throttled: 0, running: 0, pending: 0, completed: 0, failed: 0, canceled: 0 },
  );
};

export const formatDuration = (durationMs: number): string => {
  if (!Number.isFinite(durationMs) || durationMs < 0) {
    return 'N/A';
  }

  if (durationMs < 1000) {
    return `${Math.round(durationMs)}ms`;
  }

  if (durationMs < 10_000) {
    return `${(durationMs / 1000).toFixed(1)}s`;
  }

  if (durationMs < 60_000) {
    return `${Math.round(durationMs / 1000)}s`;
  }

  const roundedSeconds = Math.round(durationMs / 1000);
  const hours = Math.floor(roundedSeconds / 3600);
  const minutes = Math.floor((roundedSeconds % 3600) / 60);
  const seconds = roundedSeconds % 60;

  const parts: string[] = [];

  if (hours > 0) {
    parts.push(`${hours}h`);
  }

  if (minutes > 0) {
    parts.push(`${minutes}m`);
  }

  if (seconds > 0 || parts.length === 0) {
    parts.push(`${seconds}s`);
  }

  return parts.join(' ');
};
