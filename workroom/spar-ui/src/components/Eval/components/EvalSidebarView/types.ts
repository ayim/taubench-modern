export interface Scenario {
    scenarioId: string;
    name: string;
    description: string;
  }
  
  export interface Trial {
    trialId: string;
    status: 'pending' | 'running' | 'succeeded' | 'failed';
    errorMessage: string | null;
  }
  
  export interface ScenarioRun {
    scenarioRunId: string;
    trials: Trial[];
  }
  
  export interface EvaluationItem {
    scenario: Scenario;
    latestRun?: ScenarioRun;
    isRunning: boolean;
  }