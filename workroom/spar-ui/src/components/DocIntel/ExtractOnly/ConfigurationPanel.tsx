import { useState, useCallback, useEffect, useImperativeHandle, forwardRef } from 'react';
import { Box, Typography, useSnackbar } from '@sema4ai/components';
import { ExtractionPromptEditor } from './ExtractionPromptEditor';
import { SchemaEditor } from './SchemaEditor';
import { ProcessingLoadingState } from '../shared/components/ProcessingLoadingState';
import { FormattedJsonData } from '../shared/components/FormattedJsonData';
import type { ExtractResponse, ExtractionSchemaPayload } from '../shared/types';
import { PROCESSING_STATES } from '../shared/constants/processingStates';

/**
 * ConfigurationPanel - Phase 1 configuration UI for extract-only flow
 * Power user approach: Direct editing of extraction prompt and schema
 */

interface ConfigurationPanelProps {
  currentSchema: ExtractionSchemaPayload | null;
  extractResult: ExtractResponse | null;
  isGeneratingSchema: boolean;
  isExtracting: boolean;
  error: string | null;
  onReExtract?: (schema: ExtractionSchemaPayload, prompt: string) => Promise<void>;
  onHasChanges?: (hasChanges: boolean) => void;
  onSchemaChange?: (schema: ExtractionSchemaPayload | null) => void;
  showRawJson?: boolean;
}

export interface ConfigurationPanelRef {
  triggerReExtract: () => Promise<void>;
}

export const ConfigurationPanel = forwardRef<ConfigurationPanelRef, ConfigurationPanelProps>(
  (
    {
      currentSchema,
      extractResult,
      isGeneratingSchema,
      isExtracting,
      error,
      onReExtract,
      onHasChanges,
      onSchemaChange,
      showRawJson = false,
    },
    ref,
  ) => {
    const [currentPrompt, setCurrentPrompt] = useState('');
    const [hasChanges, setHasChanges] = useState(false);
    const { addSnackbar } = useSnackbar();

    // Notify parent about changes
    useEffect(() => {
      onHasChanges?.(hasChanges);
    }, [hasChanges, onHasChanges]);

    const handlePromptChange = useCallback((prompt: string) => {
      setCurrentPrompt(prompt);
      setHasChanges(true);
    }, []);

    const handleSchemaChange = useCallback(
      (schema: ExtractionSchemaPayload) => {
        onSchemaChange?.(schema);
        setHasChanges(true);
      },
      [onSchemaChange],
    );

    const handleReExtract = useCallback(async () => {
      if (!currentSchema || !onReExtract) return;
      try {
        await onReExtract(currentSchema, currentPrompt);
        setHasChanges(false);
      } catch (err) {
        addSnackbar({ message: `Re-extraction failed: ${err}`, variant: 'danger' });
      }
    }, [currentSchema, currentPrompt, onReExtract, addSnackbar]);

    // Expose re-extract method to parent via ref
    useImperativeHandle(
      ref,
      () => ({
        triggerReExtract: handleReExtract,
      }),
      [handleReExtract],
    );

    // Loading states
    if (isGeneratingSchema) {
      return <ProcessingLoadingState {...PROCESSING_STATES.GENERATING_SCHEMA} />;
    }

    if (isExtracting) {
      return <ProcessingLoadingState {...PROCESSING_STATES.EXTRACTING} />;
    }

    // Error state
    if (error) {
      return (
        <Box padding="$16">
          <Typography color="content.error">Error: {error}</Typography>
        </Box>
      );
    }

    // Show raw JSON view when toggle is enabled
    if (showRawJson) {
      return (
        <Box display="flex" flexDirection="column" height="100%" padding="$16" gap="$16" overflow="auto">
          {currentSchema && (
            <Box display="flex" flexDirection="column" gap="$8">
              <Typography fontSize="$16" fontWeight="bold">
                Current Schema
              </Typography>
              <FormattedJsonData
                data={currentSchema}
                downloadFileName="extraction_schema.json"
                ariaLabel="extraction-schema-json"
              />
            </Box>
          )}
          {extractResult && (
            <Box display="flex" flexDirection="column" gap="$8">
              <Typography fontSize="$16" fontWeight="bold">
                Extracted Data
              </Typography>
              <FormattedJsonData
                data={extractResult}
                downloadFileName="extracted_data.json"
                ariaLabel="extracted-data-json"
              />
            </Box>
          )}
        </Box>
      );
    }

    // Main configuration UI (Visual editor mode)
    return (
      <Box display="flex" flexDirection="column" height="100%" minHeight="0" overflow="auto">
        <Box display="flex" flexDirection="column">
          {/* Extraction Prompt Editor */}
          <Box style={{ borderBottom: '1px solid var(--sema4ai-colors-border-subtle)' }}>
            <ExtractionPromptEditor
              initialPrompt={currentPrompt}
              onChange={handlePromptChange}
              disabled={isGeneratingSchema || isExtracting}
            />
          </Box>

          {/* Schema Editor */}
          <Box flex="1" minHeight="400px">
            <SchemaEditor
              schema={currentSchema}
              onChange={handleSchemaChange}
              disabled={isGeneratingSchema || isExtracting}
            />
          </Box>
        </Box>
      </Box>
    );
  },
);

ConfigurationPanel.displayName = 'ConfigurationPanel';
