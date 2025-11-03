import type { EvaluationFilters } from '../EvaluationFilters';
import type { Scenario, ScenarioRun } from '../../../Eval/components/EvalSidebarView/types';

type SimpleEvaluationData = {
  scenario: Scenario;
  allRuns: ScenarioRun[];
};

const isDateInTimeRange = (dateString: string, timeRange: EvaluationFilters['timeRange']): boolean => {
  if (timeRange === 'all') return true;

  const date = new Date(dateString);
  const now = new Date();

  if (timeRange === 'today') {
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return date >= today;
  }

  if (timeRange === 'thisWeek') {
    const weekStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() - now.getDay());
    return date >= weekStart;
  }

  return true;
};

const doesEvaluationMatchFilters = (evaluation: SimpleEvaluationData, filters: EvaluationFilters): boolean => {
  const { timeRange, models, architectures } = filters;

  const matchingRuns = evaluation.allRuns.filter((run) => {
    if (run.created_at && !isDateInTimeRange(run.created_at, timeRange)) {
      return false;
    }

    if (models.length > 0) {
      const runModels = (run.configuration?.models as string[]) || [];
      const hasMatchingModel = models.some((filterModel) =>
        runModels.some((runModel: string) => runModel === filterModel),
      );
      if (!hasMatchingModel) {
        return false;
      }
    }

    if (architectures.length > 0) {
      const runArchitecture = run.configuration?.architecture_version as string;
      if (!runArchitecture || !architectures.includes(runArchitecture)) {
        return false;
      }
    }

    return true;
  });

  return matchingRuns.length > 0;
};

const filterEvaluations = (evaluations: SimpleEvaluationData[], filters: EvaluationFilters): SimpleEvaluationData[] => {
  if (filters.timeRange === 'all' && filters.models.length === 0 && filters.architectures.length === 0) {
    return evaluations;
  }

  return evaluations.filter((evaluation) => doesEvaluationMatchFilters(evaluation, filters));
};

export const getMatchingScenarioIds = (
  evaluations: SimpleEvaluationData[],
  filters: EvaluationFilters,
): Set<string> => {
  const filteredEvaluations = filterEvaluations(evaluations, filters);
  return new Set(filteredEvaluations.map((evaluation) => evaluation.scenario.scenario_id));
};
