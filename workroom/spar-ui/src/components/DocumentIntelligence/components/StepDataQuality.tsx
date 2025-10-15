import { Box, Typography, Button, Progress, useSnackbar } from '@sema4ai/components';
import {
  IconSparkles2,
  IconPlus,
} from '@sema4ai/icons';
import { FC, useEffect, useCallback, useState, useMemo, useRef } from 'react';
import { DocumentData } from '../types';
import { useDocumentIntelligenceStore } from '../store/useDocumentIntelligenceStore';
import type { ValidationRule } from '../store/useDocumentIntelligenceStore';
import { useDataQualityFlow } from '../hooks/useDocumentIntelligenceFlows';
import { formatSqlQuery } from '../utils/dataTransformations';
import { SpecialHandlingInstructions } from './common/SpecialHandlingInstructions';
import { QualityCheckItem } from './common/QualityCheckItem';

interface StepDataQualityProps {
  documentData: DocumentData;
  isReadOnly?: boolean;
  isProcessing?: boolean;
  processingStep?: string;
}

export const StepDataQuality: FC<StepDataQualityProps> = ({
  documentData,
  isReadOnly = false,
  isProcessing = false,
  processingStep,
}) => {
  const { fileRef, threadId, agentId } = documentData;

  const {
    dataQualityChecks,
    qualityCheckResults,
    setDataQualityChecks,
    setQualityCheckResult,
    dataModel,
    ingestedDocument,
    dataQualityPrompt,
    setDataQualityPrompt,
  } = useDocumentIntelligenceStore();

  const { executeDataQualityFlow, executeQualityChecks, isLoading: flowLoading } = useDataQualityFlow();
  const [expandedSqlSections, setExpandedSqlSections] = useState<Set<string>>(new Set());
  const [checkDescriptions, setCheckDescriptions] = useState<Record<string, string>>({});
  const [regenerateRules, setRegenerateRules] = useState<Record<string, boolean>>({});
  const [runningTests, setRunningTests] = useState<Set<string>>(new Set());
  const [regeneratingRule, setRegeneratingRule] = useState<string | null>(null);

  const initLock = useRef(false);
  const { addSnackbar } = useSnackbar();

  // Function to toggle SQL section expansion
  const toggleSqlExpansion = (ruleName: string) => {
    setExpandedSqlSections((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(ruleName)) {
        newSet.delete(ruleName);
      } else {
        newSet.add(ruleName);
      }
      return newSet;
    });
  };

  // Function to copy SQL query to clipboard
  const copyToClipboard = async (sqlQuery: string) => {
    try {
      await navigator.clipboard.writeText(sqlQuery);
      addSnackbar({ message: 'SQL query copied to clipboard', close: true });
    } catch (err) {
      // Fallback for older browsers
      try {
        const textArea = document.createElement('textarea');
        textArea.value = sqlQuery;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        addSnackbar({ message: 'SQL query copied to clipboard', close: true });
      } catch (fallbackErr) {
        addSnackbar({ message: 'Failed to copy SQL query', close: true });
      }
    }
  };

  // Handle description changes
  const handleDescriptionChange = (ruleName: string, newDescription: string) => {
    // Update local state for immediate UI feedback
    setCheckDescriptions((prev) => {
      // if the description has changed, set the regenerate rules to true
      if (prev[ruleName] !== newDescription) {
        setRegenerateRules((prevRegenerate) => ({ ...prevRegenerate, [ruleName]: true }));
      }
      return {
        ...prev,
        [ruleName]: newDescription,
      };
    });

    // Update the quality checks in store
    setDataQualityChecks(
      dataQualityChecks.map((check) =>
        check.rule_name === ruleName ? { ...check, rule_description: newDescription } : check
      )
    );
  };

  // Handle adding new quality check rule
  const handleAddQualityCheckRule = () => {
    const newRule = {
      id: `custom_check_${Date.now()}`,
      name: `Custom Check ${Date.now()}`,
      type: 'validation' as const,
      rule_name: `custom_check_${Date.now()}`,
      rule_description: '',
      sql_query: '',
    };


    setDataQualityChecks([...dataQualityChecks, newRule]);

    setCheckDescriptions((prev) => ({
      ...prev,
      [newRule.rule_name]: newRule.rule_description,
    }));
  };

  const handleDeleteQualityCheck = (ruleName: string) => {
    setDataQualityChecks(dataQualityChecks.filter((check) => check.rule_name !== ruleName));

    setCheckDescriptions((prev) => {
      const newDescriptions = { ...prev };
      delete newDescriptions[ruleName];
      return newDescriptions;
    });

    setQualityCheckResult(ruleName, null);
  };

  // Handle regenerating a quality check
  const handleRegenerateRule = useCallback(
    async (check: (typeof dataQualityChecks)[0]) => {
      const ruleName = check.rule_name as string;
      setRegeneratingRule(ruleName);
      setRegenerateRules((prev) => ({ ...prev, [ruleName]: false }));
      setQualityCheckResult(ruleName, null);

      if (!dataModel) {
        addSnackbar({ message: 'Missing required data - dataModel', close: true });
        setRegeneratingRule(null);
        return;
      }

      try {

        const currentChecks = [...dataQualityChecks];

        const result = await executeDataQualityFlow({
          agentId,
          dataModelName: dataModel.name,
          threadId,
          description: check.rule_description as string,
          limit: 1,
        });

        const newChecks = result.qualityChecks || [];
        const newCheck = newChecks[0];

        if (newCheck) {
          setDataQualityChecks(
            currentChecks.map((c) =>
              c.rule_name === check.rule_name
                ? {
                    ...c,
                    ...newCheck,
                    sql_query: newCheck.sql_query || c.sql_query,
                    rule_description: newCheck.rule_description || c.rule_description,
                  }
                : c
            )
          );
        }
      } catch (error) {
        addSnackbar({
          message: `Failed to regenerate quality check: ${error instanceof Error ? error.message : 'Unknown error'}`,
          close: true,
        });
      } finally {
        setRegeneratingRule(null);
      }
    },
    [executeDataQualityFlow, dataModel, agentId, threadId, dataQualityChecks, setDataQualityChecks, setQualityCheckResult, addSnackbar],
  );

  // Handle running a specific quality check
  const handleRunTest = useCallback(
    async (check: (typeof dataQualityChecks)[0]) => {

      setRunningTests((prev) => new Set([...prev, check.rule_name as string]));

      // Get document_id from ingestedDocument
      const documentId = (ingestedDocument?.document?.document as { id?: string })?.id;

      if (!documentId) {
        addSnackbar({
          message: 'No document ID available. Please ensure document is properly ingested.',
          close: true,
        });

        setRunningTests((prev) => {
          const newSet = new Set(prev);
          newSet.delete(check.rule_name as string);
          return newSet;
        });
        return;
      }

      try {

        // Ensure the check has all required ValidationRule properties
        const validationRule: ValidationRule = {
          rule_name: check.rule_name || '',
          rule_description: check.rule_description || '',
          sql_query: check.sql_query || '',
        };

        await executeQualityChecks({
          qualityChecks: [validationRule],
          documentId,
        });
      } catch (error) {
        addSnackbar({
          message: `Failed to execute quality check: ${error instanceof Error ? error.message : 'Unknown error'}`,
          close: true,
        });
      } finally {

        setRunningTests((prev) => {
          const newSet = new Set(prev);
          newSet.delete(check.rule_name as string);
          return newSet;
        });
      }
    },
    [executeQualityChecks, ingestedDocument, addSnackbar],
  );

  const handleInit = useCallback(async () => {
    if (initLock.current) return;
    initLock.current = true;

    try {
      if (dataQualityChecks.length === 0 && dataModel && threadId && agentId && fileRef) {
        await executeDataQualityFlow({
          agentId,
          dataModelName: dataModel.name,
          threadId,
          limit: 3,
        });
      }
    } catch (e) {
      addSnackbar({ message: `Failed to initialize data quality flow: ${e instanceof Error ? e.message : 'Unknown error'}`, close: true });
    } finally {
      initLock.current = false;
    }
  }, [executeDataQualityFlow, dataModel, threadId, agentId, fileRef, dataQualityChecks]);


  useEffect(
    () => {
      const initialDescriptions: Record<string, string> = {};
      dataQualityChecks.forEach((check) => {
        const ruleName = check.rule_name as string;
        const ruleDescription = check.rule_description as string;

        if (checkDescriptions[ruleName] !== ruleDescription) {
          initialDescriptions[ruleName] = ruleDescription;
        }
      });

      if (Object.keys(initialDescriptions).length > 0) {
        setCheckDescriptions((prev) => ({ ...prev, ...initialDescriptions }));
      }
    },

    [dataQualityChecks],
  );

  useEffect(
    () => {
      handleInit();
    },
    [],
  );

  const memoizedQualityChecks = useMemo(() => dataQualityChecks, [dataQualityChecks]);
  const memoizedQualityCheckResults = useMemo(() => qualityCheckResults, [qualityCheckResults]);


  if (isProcessing || flowLoading) {
    return (
      <Box className="h-full">
        <Box display="flex" alignItems="center" gap="$8" marginBottom="$8">
          <IconSparkles2 color="content.subtle.light" />
          <Typography fontSize="$16" fontWeight="medium" color="content.subtle.light">
            {processingStep || 'Processing document...'}
          </Typography>
        </Box>

        {/* Loading dots */}
        <Box display="flex" gap="$8">
          <Progress id="data-quality-loading" />
        </Box>
      </Box>
    );
  }

  // Show empty state if no data model
  if (!dataModel) {
    return (
      <Box display="flex" flexDirection="column" className="h-full">
        <Typography fontSize="$16" fontWeight="medium" marginBottom="$16">
          Data Quality Assessment
        </Typography>

        <Box flex="1" display="flex" alignItems="center" justifyContent="center">
          <Typography color="content.subtle">No data model available for quality assessment</Typography>
        </Box>
      </Box>
    );
  }

  // Show empty state if no data quality checks
  if (!threadId || !agentId || !fileRef || memoizedQualityChecks.length === 0) {
    return (
      <Box display="flex" flexDirection="column" className="h-full">
        <Typography fontSize="$16" fontWeight="medium" marginBottom="$16">
          Data Quality Assessment
        </Typography>

        <Box flex="1" display="flex" alignItems="center" justifyContent="center">
          <Typography color="content.subtle">No data quality checks available for quality assessment</Typography>
        </Box>
      </Box>
    );
  }

  // Show success message and quality checks list
  return (
    <Box display="flex" flexDirection="column" className="h-full pb-4">
      {/* Header message */}
      <Box marginBottom="$32" display="flex" alignItems="center" gap="$8">
        <IconSparkles2 color="content.subtle.light" />
          <Typography fontSize="$12" color="content.subtle">
            Revise, add or remove the data quality checks below or via Agent chat.
          </Typography>
      </Box>

      <SpecialHandlingInstructions
        step="data_quality"
        objectPrompt={dataQualityPrompt}
        disabled={isReadOnly}
        onUpdate={(prompt) => {
          setDataQualityPrompt(prompt);
        }}
      />

      <Box marginBottom="$32" display="flex" alignItems="center" gap="$8">
        <Box display="flex" flexDirection="column" gap="$8" marginBottom="$8">
          <Typography fontSize="$16" fontWeight="bold">
            Data quality checks
          </Typography>
           <Typography fontSize="$12" color="content.subtle">
            These rules will automatically run to verify the logical and accurate extraction of data.
          </Typography>
        </Box>
      </Box>

      {/* Quality checks list */}
      <Box display="flex" flexDirection="column" gap="$16">
        {memoizedQualityChecks.map((check, index) => {
          const ruleName = check.rule_name as string;
          const result = memoizedQualityCheckResults[ruleName];
          const isRunning = runningTests.has(ruleName);
          const isRegenerating = regeneratingRule === ruleName;
          const regenerateRule = Boolean(regenerateRules[ruleName] || false);
          const sqlQuery = check.sql_query as string;
          const hasSqlQuery = Boolean(sqlQuery && sqlQuery.trim() !== '');

          return (
            <QualityCheckItem
              key={ruleName || check.id}
              check={check}
              index={index}
              isReadOnly={isReadOnly}
              result={result}
              isRunning={isRunning}
              isRegenerating={isRegenerating}
              regenerateRule={regenerateRule}
              hasSqlQuery={hasSqlQuery}
              checkDescriptions={checkDescriptions}
              expandedSqlSections={expandedSqlSections}
              onDescriptionChange={handleDescriptionChange}
              onToggleSqlExpansion={toggleSqlExpansion}
              onDeleteQualityCheck={handleDeleteQualityCheck}
              onRegenerateRule={handleRegenerateRule}
              onRunTest={handleRunTest}
              onCopyToClipboard={copyToClipboard}
              formatSqlQuery={formatSqlQuery}
            />
          );
        })}
      </Box>

      {/* Add Quality Check Rule Button */}
      {!isReadOnly && (
        <Box marginTop="$16">
          <Button
            icon={IconPlus}
            variant="ghost"
            round
            onClick={handleAddQualityCheckRule}
            style={{
              border: '1px solid #DADEE3',
              backgroundColor: 'white',
            }}
          >
            Add Quality Check Rule
          </Button>
        </Box>
      )}

      {/* Empty state if no checks generated */}
      {memoizedQualityChecks.length === 0 && !isProcessing && (
        <Box flex="1" display="flex" alignItems="center" justifyContent="center">
          <Typography color="content.subtle">No data quality checks have been generated yet.</Typography>
        </Box>
      )}
    </Box>
  );
};
