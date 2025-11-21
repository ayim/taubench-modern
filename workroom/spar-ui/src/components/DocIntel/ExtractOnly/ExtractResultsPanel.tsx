import { FC } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { ProcessingLoadingState } from '../shared/components/ProcessingLoadingState';
import { FormattedJsonData } from '../shared/components/FormattedJsonData';
import { ExtractResponse, ExtractionSchemaPayload } from '../shared/types';
import { PROCESSING_STATES } from '../shared/constants/processingStates';

/**
 * ExtractResultsPanel - Display extraction schema and extracted data
 * Handles loading states for both schema generation and extraction steps
 */

interface ExtractResultsPanelProps {
  currentSchema: ExtractionSchemaPayload | null;
  extractResult: ExtractResponse | null;
  isGeneratingSchema: boolean;
  isExtracting: boolean;
  error: string | null;
  showRawJson: boolean;
}

export const ExtractResultsPanel: FC<ExtractResultsPanelProps> = ({
  currentSchema,
  extractResult,
  isGeneratingSchema,
  isExtracting,
  error,
  showRawJson,
}) => {
  if (isGeneratingSchema) {
    return <ProcessingLoadingState {...PROCESSING_STATES.GENERATING_SCHEMA} />;
  }

  if (isExtracting) {
    return <ProcessingLoadingState {...PROCESSING_STATES.EXTRACTING} />;
  }

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
        <FormattedJsonData
          data={currentSchema}
          downloadFileName="extraction_schema.json"
          ariaLabel="extraction-schema-json"
        />
      </Box>
    );
  }

  // Show extracted data
  if (extractResult) {
    const dataToDisplay = extractResult.result || extractResult;
    return (
      <Box padding="$16" display="flex" flexDirection="column" gap="$16" overflow="auto" flex="1">
        {!showRawJson && (
          <Typography fontSize="$16" fontWeight="bold">
            Extracted Data
          </Typography>
        )}
        <FormattedJsonData
          data={dataToDisplay}
          downloadFileName="extracted_data.json"
          ariaLabel="extracted-data-json"
        />
      </Box>
    );
  }

  // Empty state
  return (
    <Box padding="$16" display="flex" alignItems="center" justifyContent="center" height="100%">
      <Typography color="content.subtle">No extraction results yet</Typography>
    </Box>
  );
};
