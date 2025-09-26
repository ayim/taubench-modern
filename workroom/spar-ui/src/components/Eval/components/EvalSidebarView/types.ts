import type { components } from '@sema4ai/agent-server-interface';

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