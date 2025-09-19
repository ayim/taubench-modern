import { components } from "@sema4ai/agent-server-interface";
import { Scenario } from "../queries/evals";

type Trial = components['schemas']['Trial'];

export const transformAgentServerScenarios = (
    scenarios: Scenario[],
    latestRunsData: (components['schemas']['ScenarioRun'] | null)[],
  ) => {
    return scenarios.map((apiScenario, index) => {
      const latestRunQuery = latestRunsData[index];
  
      const isRunning =
        latestRunQuery?.trials?.some((trial: Trial) => trial.status === 'PENDING' || trial.status === 'EXECUTING') ??
        false;
  
      return {
        scenario: {
          scenarioId: apiScenario.scenario_id,
          name: apiScenario.name,
          description: apiScenario.description,
          threadId: apiScenario.thread_id,
          messages: apiScenario.messages,
        },
        latestRun: latestRunQuery
          ? {
              scenarioRunId: latestRunQuery.scenario_run_id,
              scenarioId: latestRunQuery.scenario_id,
              numTrials: latestRunQuery.num_trials,
              trials:
                latestRunQuery.trials?.map((trial: Trial) => ({
                  trialId: trial.trial_id,
                  status: trial.status,
                  errorMessage: trial.error_message ?? null,
                  threadId: trial.thread_id ?? null,
                  statusUpdatedAt: trial.status_updated_at ?? null,
                  evaluationResults:
                    trial.evaluation_results?.map((result) => ({
                      kind: result.kind as 'response_accuracy' | 'flow_adherence' | 'action_calling',
                      passed: result.passed,
                      score: 'score' in result ? result.score : undefined,
                      explanation: 'explanation' in result ? result.explanation : undefined,
                      issues: 'issues' in result ? result.issues : undefined,
                    })) || [],
                })) || [],
            }
          : null,
        isRunning,
      };
    });
  };
  