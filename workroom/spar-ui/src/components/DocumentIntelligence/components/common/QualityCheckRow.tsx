import { Box, Typography, Input, Button, Badge, Code } from '@sema4ai/components';
import {
  IconChemicalTube,
  IconChevronDown,
  IconCheckCircle,
  IconTrash,
  IconDatabase,
  IconChevronUp,
  IconCopy,
  IconCloseCircle,
  IconRefresh,
  IconLoading,
} from '@sema4ai/icons';
import { FC, useMemo } from 'react';
import { sql } from '@codemirror/lang-sql';
import { EditorView } from '@codemirror/view';

export interface DataQualityCheck {
  rule_name: string;
  rule_description: string;
  sql_query: string;
}

export interface QualityCheckResult {
  passed: boolean;
  message?: string;
  details?: Record<string, unknown>;
}

interface QualityCheckRowProps {
  check: DataQualityCheck;
  result?: QualityCheckResult;
  index: number;
  isReadOnly?: boolean;
  isRunning?: boolean;
  isRegenerating?: boolean;
  regenerateRule?: boolean;
  expandedSqlSections: Set<string>;
  checkDescriptions: Record<string, string>;
  onDescriptionChange: (ruleName: string, description: string) => void;
  onToggleSqlExpansion: (ruleName: string) => void;
  onDeleteCheck: (ruleName: string) => void;
  onRunTest: (check: DataQualityCheck) => void;
  onRegenerateRule: (check: DataQualityCheck) => void;
  onCopySql: (sqlQuery: string) => void;
}

export const QualityCheckRow: FC<QualityCheckRowProps> = ({
  check,
  result,
  index,
  isReadOnly = false,
  isRunning = false,
  isRegenerating = false,
  regenerateRule = false,
  expandedSqlSections,
  checkDescriptions,
  onDescriptionChange,
  onToggleSqlExpansion,
  onDeleteCheck,
  onRunTest,
  onRegenerateRule,
  onCopySql,
}) => {
  const hasSqlQuery = check.sql_query && check.sql_query.trim() !== '';
  const isSuccess = result?.passed;
  const isExpanded = expandedSqlSections.has(check.rule_name);

  const getButtonIcon = () => {
    if (isRunning) return undefined;
    if (regenerateRule) return IconRefresh;
    return IconChemicalTube;
  };

  const getButtonText = () => {
    if (isRegenerating) return 'Regenerating...';
    if (regenerateRule) return 'Regenerate';
    if (isRunning) return 'Running Test...';
    if (result) return 'Re-run Test';
    return 'Run Test';
  };

  const getBadgeLabel = () => {
    if (isRunning) return 'Running';
    if (isSuccess) return 'Success';
    return 'Failed';
  };

  const getBadgeVariant = () => {
    if (isRunning) return 'orange';
    if (isSuccess) return 'green';
    return 'red';
  };

  const getBadgeIcon = () => {
    if (isRunning) return IconLoading;
    if (isSuccess) return IconCheckCircle;
    return IconCloseCircle;
  };

  // SQL editor extensions with proper syntax highlighting
  const sqlExtensions = useMemo(
    () => [
      sql(),
      EditorView.theme({
        '&': {
          fontSize: '12px !important',
        },
        '.cm-editor': {
          fontSize: '12px !important',
        },
        '.cm-content': {
          lineHeight: '1.4 !important',
          fontFamily: 'monospace',
        },
        // SQL syntax highlighting styles
        '.cm-keyword': {
          color: '#0066CC !important',
          fontWeight: 'bold',
        },
        '.cm-string': {
          color: '#006600 !important',
        },
        '.cm-number': {
          color: '#FF6600 !important',
        },
        '.cm-operator': {
          color: '#666666 !important',
        },
        '.cm-comment': {
          color: '#888888 !important',
          fontStyle: 'italic',
        },
        '.cm-punctuation': {
          color: '#333333 !important',
        },
        '.cm-builtin': {
          color: '#7B68EE !important',
        },
        // Additional SQL variable highlighting
        '.cm-variable': {
          color: '#E91E63 !important',
          fontWeight: '500',
        },
        '.cm-variableName': {
          color: '#E91E63 !important',
          fontWeight: '500',
        },
      }),
    ],
    [],
  );

  // Function to format SQL query for display
  const formatSqlQuery = (sqlQuery: string): string => {
    if (!sqlQuery) return '';

    // Simple SQL formatter to add line breaks for better readability
    return sqlQuery
      .replace(/\s+/g, ' ') // Normalize whitespace
      .replace(/\bSELECT\b/gi, 'SELECT\n  ')
      .replace(/\bFROM\b/gi, '\nFROM\n  ')
      .replace(/\bWHERE\b/gi, '\nWHERE\n  ')
      .replace(/\bGROUP BY\b/gi, '\nGROUP BY\n  ')
      .replace(/\bORDER BY\b/gi, '\nORDER BY\n  ')
      .replace(/\bHAVING\b/gi, '\nHAVING\n  ')
      .replace(/\bAND\b/gi, '\n  AND ')
      .replace(/\bOR\b/gi, '\n  OR ')
      .replace(/,(?!\s*\))/g, ',\n  ') // Add line breaks after commas (except before closing parenthesis)
      .trim();
  };

  return (
    <Box display="flex" flexDirection="column" gap="$16">
      {/* Check description */}
      <Box display="flex" alignItems="flex-start" gap="$8">
        <Typography fontSize="$16" marginTop="$8">
          {index + 1}.
        </Typography>
        <Box flex="1">
          {!isReadOnly && (
            <Input
              label=""
              value={checkDescriptions[check.rule_name] || check.rule_description}
              onChange={(e) => onDescriptionChange(check.rule_name, e.target.value)}
              placeholder="Enter quality check description"
              style={{ width: '100%', fontSize: '14px', lineHeight: '1.5' }}
              rows={3}
            />
          )}
          {isReadOnly && (
            <Typography fontSize="$16" marginTop="$8">
              {checkDescriptions[check.rule_name] || check.rule_description}
            </Typography>
          )}
        </Box>
      </Box>

      {/* Action buttons row */}
      <Box display="flex" alignItems="center" justifyContent="flex-end" gap="$8">
        {/* Conditional Success button - only show if test has results */}
        {result && !isRegenerating && (
          <Badge label={getBadgeLabel()} variant={getBadgeVariant()} icon={getBadgeIcon()} />
        )}

        {/* SQL button - inline with other buttons */}
        {hasSqlQuery && !isReadOnly && (
          <Button
            onClick={() => onToggleSqlExpansion(check.rule_name)}
            variant="ghost"
            size="small"
            round
            icon={isRegenerating || isRunning ? IconLoading : IconDatabase}
            iconAfter={isExpanded ? IconChevronDown : IconChevronUp}
            disabled={isRegenerating || isRunning}
          >
            SQL
          </Button>
        )}

        {/* Trash button */}
        {!isReadOnly && (
          <Button
            onClick={() => onDeleteCheck(check.rule_name)}
            icon={IconTrash}
            variant="outline"
            size="small"
            round
            aria-label="Delete quality check"
            disabled={isRegenerating || isRunning}
          />
        )}

        {/* Run Test button */}
        <Button
          onClick={regenerateRule ? () => onRegenerateRule(check) : () => onRunTest(check)}
          icon={getButtonIcon()}
          variant="outline"
          round
          disabled={isRegenerating || isRunning}
          loading={isRegenerating || isRunning}
          size="small"
        >
          {getButtonText()}
        </Button>
      </Box>

      {/* SQL Query Content - conditionally rendered below the buttons row */}
      {hasSqlQuery && isExpanded && !isReadOnly && (
        <Box display="flex" flexDirection="column" gap="$8">
          <Box display="flex" justifyContent="flex-end">
            <Button
              onClick={() => onCopySql(check.sql_query)}
              variant="ghost"
              size="small"
              round
              icon={IconCopy}
              aria-label="Copy SQL query to clipboard"
            />
          </Box>
          <Code
            aria-label="SQL Query"
            theme="light"
            value={formatSqlQuery(check.sql_query)}
            extensions={sqlExtensions}
            lineNumbers={false}
            readOnly
            maxRows={15}
          />
        </Box>
      )}
    </Box>
  );
};
