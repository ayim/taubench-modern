import { FC } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { ProcessingLoadingState } from '../shared/components/ProcessingLoadingState';
import { FormattedJsonData } from '../shared/components/FormattedJsonData';
import { DocumentResultsRenderer } from '../shared/components/DocumentResultsRenderer';
import { SimpleExtractResponse, ExtractionSchemaPayload } from '../shared/types';
import { PROCESSING_STATES } from '../shared/constants/processingStates';
import type { ParsedBlock } from '../shared/components/DocumentResultsRenderer';

/**
 * ExtractResultsPanel - Display extraction results UI for extract-only flow
 * Handles loading states, error states, and displays extraction results
 */

interface ExtractResultsPanelProps {
  currentSchema: ExtractionSchemaPayload | null;
  extractResult: SimpleExtractResponse | null;
  extractedBlocks?: ParsedBlock[];
  isGeneratingSchema: boolean;
  isExtracting: boolean;
  error: string | null;
  showRawJson: boolean;
  selectedBlockId?: string | null;
  onBlockClick?: (blockId: string) => void;
}

export const ExtractResultsPanel: FC<ExtractResultsPanelProps> = ({
  currentSchema,
  extractResult,
  extractedBlocks = [],
  isGeneratingSchema,
  isExtracting,
  error,
  showRawJson,
  selectedBlockId,
  onBlockClick,
}) => {
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

  // Show schema result first (before extraction)
  if (currentSchema && !extractResult) {
    return (
      <Box padding="$16" display="flex" flexDirection="column" gap="$16">
        <Typography fontSize="$16" fontWeight="bold">
          Generated Schema
        </Typography>
        <FormattedJsonData data={currentSchema} variant="extraction-schema" />
      </Box>
    );
  }

  // Show extracted data
  if (extractResult) {
    if (!extractedBlocks || extractedBlocks.length === 0) {
      return (
        <Box display="flex" alignItems="center" justifyContent="center" flex="1" padding="$32">
          <Typography color="content.subtle">
            {isExtracting
              ? 'Extracting data...'
              : 'No extraction results yet. Generate a schema and extract data to see results.'}
          </Typography>
        </Box>
      );
    }

    // Raw JSON view
    if (showRawJson) {
      const dataToDisplay = extractResult.results || extractResult;
      return (
        <Box padding="$24" display="flex" flexDirection="column" height="100%" overflow="auto">
          <FormattedJsonData data={dataToDisplay} variant="extraction-data" />
        </Box>
      );
    }

    // Interactive results view with DocumentResultsRenderer
    return (
      <DocumentResultsRenderer
        blocks={extractedBlocks}
        selectedBlockId={selectedBlockId}
        onBlockClick={onBlockClick}
        title="Extracted fields are shown below. Click a field to highlight its location in the PDF."
      />
    );
  }

  return (
    <Box padding="$16" display="flex" alignItems="center" justifyContent="center" height="100%">
      <Typography color="content.subtle">No extraction results yet</Typography>
    </Box>
  );
};
