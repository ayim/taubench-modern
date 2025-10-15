import { Box, Typography, Input, Badge, Button, Code, EditorView } from '@sema4ai/components';
import { sql } from '@codemirror/lang-sql';
import {
  IconChemicalTube,
  IconChevronDown,
  IconCheckCircle,
  IconLoading,
  IconTrash,
  IconDatabase,
  IconChevronUp,
  IconCopy,
  IconCloseCircle,
  IconRefresh,
} from '@sema4ai/icons';
import { FC, useMemo } from 'react';

// Types for quality check components
interface QualityCheckItemProps {
  check: {
    id: string;
    name: string;
    type: string;
    rule_name?: string;
    rule_description?: string;
    sql_query?: string;
    [key: string]: unknown;
  };
  index: number;
  isReadOnly: boolean;
  result?: { passed: boolean } | null;
  isRunning: boolean;
  isRegenerating: boolean;
  regenerateRule: boolean;
  hasSqlQuery: boolean;
  checkDescriptions: Record<string, string>;
  expandedSqlSections: Set<string>;
  onDescriptionChange: (ruleName: string, description: string) => void;
  onToggleSqlExpansion: (ruleName: string) => void;
  onDeleteQualityCheck: (ruleName: string) => void;
  onRegenerateRule: (check: QualityCheckItemProps['check']) => void;
  onRunTest: (check: QualityCheckItemProps['check']) => void;
  onCopyToClipboard: (sqlQuery: string) => void;
  formatSqlQuery: (sqlQuery: string) => string;
}

interface ActionButtonsProps {
  check: QualityCheckItemProps['check'];
  result?: { passed: boolean } | null;
  isRunning: boolean;
  isRegenerating: boolean;
  regenerateRule: boolean;
  hasSqlQuery: boolean;
  isReadOnly: boolean;
  expandedSqlSections: Set<string>;
  onToggleSqlExpansion: (ruleName: string) => void;
  onDeleteQualityCheck: (ruleName: string) => void;
  onRegenerateRule: (check: QualityCheckItemProps['check']) => void;
  onRunTest: (check: QualityCheckItemProps['check']) => void;
}

interface SqlSectionProps {
  check: QualityCheckItemProps['check'];
  isReadOnly: boolean;
  expandedSqlSections: Set<string>;
  onCopyToClipboard: (sqlQuery: string) => void;
  formatSqlQuery: (sqlQuery: string) => string;
}

// Action Buttons Component
const ActionButtons: FC<ActionButtonsProps> = ({
  check,
  result,
  isRunning,
  isRegenerating,
  regenerateRule,
  hasSqlQuery,
  isReadOnly,
  expandedSqlSections,
  onToggleSqlExpansion,
  onDeleteQualityCheck,
  onRegenerateRule,
  onRunTest,
}) => {
  const isSuccess = result?.passed;
  const ruleName = check.rule_name as string;
  const isExpanded = expandedSqlSections.has(ruleName);

  const getButtonText = () => {
    if (isRegenerating) return 'Regenerating...';
    if (regenerateRule) return 'Regenerate';
    if (isRunning) return 'Running Test...';
    if (result) return 'Re-run Test';
    return 'Run Test';
  };

  const getButtonIcon = () => {
    if (isRunning) return undefined;
    if (regenerateRule) return IconRefresh;
    return IconChemicalTube;
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

  return (
    <Box display="flex" alignItems="center" justifyContent="flex-end" gap="$8">
      {/* Conditional Success button - only show if test has results */}
      {result && !isRegenerating && (
        <Badge
          label={getBadgeLabel()}
          variant={getBadgeVariant()}
          icon={getBadgeIcon()}
        />
      )}

      {/* SQL button - inline with other buttons */}
      {hasSqlQuery && !isReadOnly && (
        <Button
          onClick={() => onToggleSqlExpansion(ruleName)}
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
          onClick={() => onDeleteQualityCheck(ruleName)}
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
  );
};

// SQL Section Component
const SqlSection: FC<SqlSectionProps> = ({
  check,
  isReadOnly,
  expandedSqlSections,
  onCopyToClipboard,
  formatSqlQuery,
}) => {
  const ruleName = check.rule_name as string;
  const sqlQuery = check.sql_query as string;
  const isExpanded = expandedSqlSections.has(ruleName);

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

  if (!isExpanded || isReadOnly) {
    return null;
  }

  return (
    <Box display="flex" flexDirection="column" gap="$8">
      <Box display="flex" justifyContent="flex-end">
        <Button
          onClick={() => onCopyToClipboard(sqlQuery)}
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
        value={formatSqlQuery(sqlQuery)}
        extensions={sqlExtensions}
        lineNumbers={false}
        readOnly
        maxRows={15}
      />
    </Box>
  );
};

// Main Quality Check Item Component
export const QualityCheckItem: FC<QualityCheckItemProps> = ({
  check,
  index,
  isReadOnly,
  result,
  isRunning,
  isRegenerating,
  regenerateRule,
  hasSqlQuery,
  checkDescriptions,
  expandedSqlSections,
  onDescriptionChange,
  onToggleSqlExpansion,
  onDeleteQualityCheck,
  onRegenerateRule,
  onRunTest,
  onCopyToClipboard,
  formatSqlQuery,
}) => {
  const ruleName = check.rule_name as string;
  const ruleDescription = check.rule_description as string;
  const currentDescription = checkDescriptions[ruleName] || ruleDescription;

  return (
    <Box display="flex" flexDirection="column" gap="$16">
      {/* Check description */}
      <Box display="flex" alignItems="flex-start" gap="$8">
        <Typography fontSize="$16" marginTop="$8">
          {index + 1}.
        </Typography>
        <Box flex="1">
          {!isReadOnly ? (
            <Input
              label=""
              value={currentDescription}
              onChange={(e) => onDescriptionChange(ruleName, e.target.value)}
              placeholder="Enter quality check description"
              className="w-full"
              rows={3}
              style={{ fontSize: '14px', lineHeight: '1.5' }}
            />
          ) : (
            <Typography fontSize="$16" marginTop="$8">
              {currentDescription}
            </Typography>
          )}
        </Box>
      </Box>

      {/* Action buttons row */}
      <ActionButtons
        check={check}
        result={result}
        isRunning={isRunning}
        isRegenerating={isRegenerating}
        regenerateRule={regenerateRule}
        hasSqlQuery={hasSqlQuery}
        isReadOnly={isReadOnly}
        expandedSqlSections={expandedSqlSections}
        onToggleSqlExpansion={onToggleSqlExpansion}
        onDeleteQualityCheck={onDeleteQualityCheck}
        onRegenerateRule={onRegenerateRule}
        onRunTest={onRunTest}
      />

      {/* SQL Query Content */}
      <SqlSection
        check={check}
        isReadOnly={isReadOnly}
        expandedSqlSections={expandedSqlSections}
        onCopyToClipboard={onCopyToClipboard}
        formatSqlQuery={formatSqlQuery}
      />
    </Box>
  );
};
