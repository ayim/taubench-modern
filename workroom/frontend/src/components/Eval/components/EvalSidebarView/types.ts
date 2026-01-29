import type { components } from '@sema4ai/agent-server-interface';
import type { ScenarioBatchRunMetadata, ScenarioBatchRunStatistics, ScenarioBatchRunStatus } from '~/queries/evals';

// Use raw API types directly
export type Scenario = components['schemas']['Scenario'];
export type ScenarioRun = components['schemas']['ScenarioRun'];
export type Trial = components['schemas']['Trial'];
// EvaluationResult is a union type in the API schemas, not a single type
export type EvaluationResult =
  | components['schemas']['ResponseAccuracyResult']
  | components['schemas']['FlowAdherenceResult']
  | components['schemas']['ActionCallingResult'];

// Simple interface for the evaluation item that combines API data with UI state
export interface EvaluationItem {
  scenario: Scenario;
  latestRun: ScenarioRun | null;
  allRuns: ScenarioRun[];
  currentRunIndex: number;
  currentRun: ScenarioRun | null;
  isRunning: boolean;
}

export interface BatchSummary {
  batchRunId: string;
  createdAt: string;
  status: ScenarioBatchRunStatus;
  statistics: ScenarioBatchRunStatistics;
  numTrials: number;
  metadata: ScenarioBatchRunMetadata | null;
  scenarioIssues?: Record<
    string,
    {
      name: string;
      stalled: number;
      slow: number;
    }
  >;
}
