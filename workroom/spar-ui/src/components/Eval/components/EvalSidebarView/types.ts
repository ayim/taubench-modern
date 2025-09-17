export interface Scenario {
    scenarioId: string;
    name: string;
    description: string;
    threadId: string | null;
  }

  export interface EvaluationResult {
    kind: 'response_accuracy' | 'flow_adherence' | 'action_calling';
    passed: boolean;
    score?: number;
    explanation?: string;
    issues?: string[];
  }
  
  export interface Trial {
    trialId: string;
    status: "PENDING" | "EXECUTING" | "COMPLETED" | "ERROR" | "CANCELED"
    errorMessage: string | null;
    threadId: string | null;
    statusUpdatedAt: string | null;
    evaluationResults: EvaluationResult[];
  }
  
  export interface ScenarioRun {
    scenarioRunId: string;
    trials: Trial[];
  }
  
  export interface EvaluationItem {
    scenario: Scenario;
    latestRun: ScenarioRun | null;
    isRunning: boolean;
  }