import { FC, useMemo } from 'react';
import { Box, Typography, Checkbox, Button } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { IconTrash } from '@sema4ai/icons';

import type { Scenario, ScenarioRun } from '../../Eval/components/EvalSidebarView/types';

const FilterSection = styled(Box)`
  border-bottom: 1px solid ${({ theme }) => theme.colors.border.subtle.color};
  padding: ${({ theme }) => theme.space.$12} 0;

  &:last-child {
    border-bottom: none;
  }
`;

export interface EvaluationFilters {
  timeRange: 'all' | 'today' | 'thisWeek';
  models: string[];
  architectures: string[];
}

export interface EvaluationFiltersProps {
  evaluationData: {
    evaluations: {
      scenario: Scenario;
      allRuns: ScenarioRun[];
    }[];
    loading: boolean;
  };
  filters: EvaluationFilters;
  onFiltersChange: (filters: EvaluationFilters) => void;
  onClearAll: () => void;
}

export const EvaluationFiltersComponent: FC<EvaluationFiltersProps> = ({
  evaluationData,
  filters,
  onFiltersChange,
  onClearAll,
}) => {
  const { availableModels, availableArchitectures } = useMemo(() => {
    const models = new Set<string>();
    const architectures = new Set<string>();

    evaluationData.evaluations.forEach(({ allRuns }) => {
      allRuns.forEach((run) => {
        if (run.configuration?.models && Array.isArray(run.configuration.models)) {
          run.configuration.models.forEach((model: string) => models.add(model));
        }

        if (run.configuration?.architecture_version && typeof run.configuration.architecture_version === 'string') {
          architectures.add(run.configuration.architecture_version);
        }
      });
    });

    return {
      availableModels: Array.from(models).sort(),
      availableArchitectures: Array.from(architectures).sort(),
    };
  }, [evaluationData.evaluations]);

  const handleTimeRangeChange = (timeRange: EvaluationFilters['timeRange']) => {
    onFiltersChange({ ...filters, timeRange });
  };

  const handleModelToggle = (model: string) => {
    const newModels = filters.models.includes(model)
      ? filters.models.filter((m) => m !== model)
      : [...filters.models, model];

    onFiltersChange({ ...filters, models: newModels });
  };

  const handleArchitectureToggle = (architecture: string) => {
    const newArchitectures = filters.architectures.includes(architecture)
      ? filters.architectures.filter((a) => a !== architecture)
      : [...filters.architectures, architecture];

    onFiltersChange({ ...filters, architectures: newArchitectures });
  };

  const hasActiveFilters = filters.timeRange !== 'all' || filters.models.length > 0 || filters.architectures.length > 0;

  return (
    <Box p="$12">
      <FilterSection>
        <Typography variant="body-small" fontWeight="medium" mb="$6">
          Time Range
        </Typography>
        <Box display="flex" flexDirection="column" gap="$6">
          <Checkbox label="All" checked={filters.timeRange === 'all'} onChange={() => handleTimeRangeChange('all')} />
          <Checkbox
            label="Today"
            checked={filters.timeRange === 'today'}
            onChange={() => handleTimeRangeChange('today')}
          />
          <Checkbox
            label="This Week"
            checked={filters.timeRange === 'thisWeek'}
            onChange={() => handleTimeRangeChange('thisWeek')}
          />
        </Box>
      </FilterSection>

      {availableModels.length > 0 && (
        <FilterSection>
          <Typography variant="body-small" fontWeight="medium" mb="$6">
            Models
          </Typography>
          <Box display="flex" flexDirection="column" gap="$6">
            {availableModels.map((model) => (
              <Checkbox
                key={model}
                label={model}
                checked={filters.models.includes(model)}
                onChange={() => handleModelToggle(model)}
              />
            ))}
          </Box>
        </FilterSection>
      )}

      {availableArchitectures.length > 0 && (
        <FilterSection>
          <Typography variant="body-small" fontWeight="medium" mb="$6">
            Architecture Versions
          </Typography>
          <Box display="flex" flexDirection="column" gap="$6">
            {availableArchitectures.map((architecture) => (
              <Checkbox
                key={architecture}
                label={`v${architecture}`}
                checked={filters.architectures.includes(architecture)}
                onChange={() => handleArchitectureToggle(architecture)}
              />
            ))}
          </Box>
        </FilterSection>
      )}

      {hasActiveFilters && (
        <Box marginTop="$8" display="flex" justifyContent="flex-end">
          <Button variant="ghost-subtle" size="small" icon={IconTrash} onClick={onClearAll}>
            Clear
          </Button>
        </Box>
      )}
    </Box>
  );
};
