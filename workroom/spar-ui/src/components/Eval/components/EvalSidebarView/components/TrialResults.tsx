import React, { FC } from 'react';
import { Box, Button, Typography, Badge } from '@sema4ai/components';
import {
  IconStatusCompleted,
  IconStatusError,
  IconChevronDown,
  IconChevronRight,
  IconShare,
  IconInformation,
  IconLoading,
} from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { getEvaluationResultColor, getEvaluationResultLabel, getEvaluationResultIcon, isTrialTerminal } from '../utils';
import type { Trial } from '../types';

const ErrorMessageBox = styled.pre`
  margin: 0;
  padding: ${({ theme }) => theme.space.$8};
  background-color: #fee2e2;
  border-radius: ${({ theme }) => theme.radii.$4};
  font-size: ${({ theme }) => theme.fontSizes.$12};
  font-family: ${({ theme }) => theme.fonts.code};
  white-space: pre-wrap;
  word-break: break-word;
  color: #991b1b;
  user-select: text;
  cursor: text;
`;

export interface TrialResultsProps {
  scenarioId: string;
  trial: Trial;
  trialIndex: number;
  expandedTrials: Set<string>;
  expandedEvaluations: Set<string>;
  onToggleTrialDetails: (trialKey: string) => void;
  onToggleEvaluationDetails: (evaluationKey: string) => void;
  onViewResults: (trial: { threadId: string }) => void;
}

export const TrialResults: FC<TrialResultsProps> = ({
  scenarioId,
  trial,
  trialIndex,
  expandedTrials,
  expandedEvaluations,
  onToggleTrialDetails,
  onToggleEvaluationDetails,
  onViewResults,
}) => {
  const trialKey = `${scenarioId}-${trial.trial_id}`;
  const isTrialExpanded = expandedTrials.has(trialKey);
  const isTrialCompleted = isTrialTerminal(trial);
  const hasEvaluationResults = isTrialCompleted && trial.evaluation_results && trial.evaluation_results.length > 0;

  const getTrialStatusBadges = () => {
    if (trial.status === 'PENDING') {
      return (  
        <Badge
          icon={IconLoading}
          iconColor="blue80"
          variant="info"
          size="small"
          label="Pending"
        />
      );
    }

    if (trial.status === 'EXECUTING') {
      return (  
        <Badge
          icon={IconLoading}
          iconColor="yellow80"
          variant="yellow"
          size="small"
          label="Running"
        />
      );
    }

    if (trial.status === 'CANCELED') {
      return (
        <Badge
          icon={IconInformation}
          iconColor="yellow80"
          variant="yellow"
          size="small"
          label="Canceled"
        />
      );
    }

    if (trial.status === 'ERROR') {
      return (
        <Badge
          icon={IconStatusError}
          iconColor="content.error"
          variant="red"
          size="small"
          label="Error"
        />
      );
    }

    if (trial.status === 'COMPLETED') {
      const passedCount = trial.evaluation_results?.filter(result => result.passed).length || 0;
      const failedCount = trial.evaluation_results?.filter(result => !result.passed).length || 0;

      const badges = [];

      if (passedCount > 0) {
        badges.push(
          <Badge
            key="passed"
            icon={IconStatusCompleted}
            iconColor="content.success"
            variant="green"
            size="small"
            label={`${passedCount}`}
          />
        );
      }

      if (failedCount > 0) {
        badges.push(
          <Badge
            key="failed"
            icon={IconStatusError}
            iconColor="content.error"
            variant="red"
            size="small"
            label={`${failedCount}`}
          />
        );
      }

      if (badges.length === 0) {
        return (
          <Badge
            icon={IconStatusError}
            iconColor="content.error"
            variant="red"
            size="small"
            label="No Results"
          />
        );
      }

      return badges;
    }

    return null;
  };

  const hasTrialError = trial.status === 'ERROR' && trial.error_message;
  const hasExpandableContent = hasEvaluationResults || hasTrialError;

  return (
    <Box display="flex" flexDirection="column" gap="$4">
      <Box display="flex" alignItems="center" gap="$8">
        <Typography variant="body-small" fontWeight="medium">
          {`Test ${trialIndex + 1} results`}
        </Typography>
        <Box display="flex" gap="$4">
          {getTrialStatusBadges()}
        </Box>
        {hasExpandableContent && (
          <Button
            variant="ghost"
            size="small"
            icon={isTrialExpanded ? IconChevronDown : IconChevronRight}
            onClick={() => onToggleTrialDetails(trialKey)}
            aria-label="Toggle trial details"
          />
        )}
        {trial.thread_id && (
          <Button
            variant="ghost"
            round
            size="small"
            icon={IconShare}
            onClick={() => onViewResults({ threadId: trial.thread_id! })}
            aria-label="Navigate to thread"
          />
        )}
      </Box>

      {isTrialExpanded && isTrialCompleted && (
        <Box paddingLeft="$16" display="flex" flexDirection="column" gap="$8">
          {hasTrialError && (
            <Box display="flex" flexDirection="column" gap="$4">
              <Box display="flex" alignItems="center" gap="$8">
                <IconStatusError size={16} color="content.error" />
                <Typography variant="body-small" fontWeight="medium" color="content.error">
                  Trial Error
                </Typography>
              </Box>
              <ErrorMessageBox>
                {trial.error_message}
              </ErrorMessageBox>
            </Box>
          )}

          {trial.evaluation_results && trial.evaluation_results.length > 0 ? (
            trial.evaluation_results?.map((result) => {
              const evaluationKey = `${trial.trial_id}-${result.kind}`;
              const isExpanded = expandedEvaluations.has(evaluationKey);
              const hasDetails = ('explanation' in result && result.explanation) || ('issues' in result && result.issues && result.issues.length > 0);
              
              return (
                <Box key={evaluationKey} display="flex" flexDirection="column" gap="$4">
                  <Box display="flex" alignItems="center" gap="$8">
                    <Typography variant="body-small" fontWeight="medium">
                      {getEvaluationResultLabel(result)}
                    </Typography>
                    {React.createElement(getEvaluationResultIcon(result), { 
                      size: 20, 
                      color: getEvaluationResultColor(result) 
                    })}
                    <Button
                      variant="ghost"
                      size="small"
                      icon={isExpanded ? IconChevronDown : IconChevronRight}
                      onClick={() => onToggleEvaluationDetails(evaluationKey)}
                      disabled={!hasDetails}
                      aria-label="Toggle evaluation details"
                    />
                  </Box>
                  {isExpanded && hasDetails && (
                    <Box paddingLeft="$14" display="flex" flexDirection="column" gap="$4" style={{ userSelect: 'text', cursor: 'text' }}>
                      {'explanation' in result && result.explanation && (
                        <Typography variant="body-small" color="content.subtle" style={{ userSelect: 'text' }}>
                          {result.explanation}
                        </Typography>
                      )}
                      {'issues' in result && result.issues && result.issues.length > 0 && (
                        <Box display="flex" flexDirection="column" gap="$2" style={{ userSelect: 'text' }}>
                          {result.issues.map((issue: string) => (
                            <Typography variant="body-small" color="content.error" style={{ userSelect: 'text' }}>
                              • {issue}
                            </Typography>
                          ))}
                        </Box>
                      )}
                    </Box>
                  )}
                </Box>
              );
            })
          ) : (
            !hasTrialError && (
              <Box display="flex" alignItems="center" gap="$8">
                <IconInformation size={16} color="content.subtle" />
                <Typography variant="body-small" color="content.subtle">
                  No evaluation results available for this run
                </Typography>
              </Box>
            )
          )}
        </Box>
      )}
    </Box>
  );
};
