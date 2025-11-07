import { FC } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { ProcessingLoadingState } from '../shared/components/ProcessingLoadingState';
import { ParseResultsSummary } from './ParseResultsSummary';
import { FormattedJsonData } from '../shared/components/FormattedJsonData';
import { ParseResponse } from '../shared/types';

/**
 * ParseResultsPanel - Display parsed document results
 * Toggles between summary view and raw JSON view based on showRawJson prop
 */

interface ParseResultsPanelProps {
  parseResult: ParseResponse | null;
  isLoading: boolean;
  error: string | null;
  showRawJson: boolean;
}

export const ParseResultsPanel: FC<ParseResultsPanelProps> = ({ parseResult, isLoading, error, showRawJson }) => {
  if (isLoading) {
    return <ProcessingLoadingState title="Parsing your document" />;
  }

  if (error) {
    return (
      <Box padding="$16">
        <Typography color="content.error">Error: {error}</Typography>
      </Box>
    );
  }

  if (!parseResult) {
    return (
      <Box padding="$16" display="flex" alignItems="center" justifyContent="center" height="100%">
        <Typography color="content.subtle">No parse results yet</Typography>
      </Box>
    );
  }

  // Extract chunks from the parse result
  const chunks = parseResult.result?.chunks;

  if (!chunks) {
    return (
      <Box padding="$16" display="flex" alignItems="center" justifyContent="center" height="100%">
        <Typography color="content.subtle">No parse results available</Typography>
      </Box>
    );
  }

  // Toggle between summary view and raw JSON view
  return showRawJson ? (
    <FormattedJsonData data={parseResult} downloadFileName="parse_results.json" ariaLabel="parse-results-json" />
  ) : (
    <ParseResultsSummary parseResult={chunks} />
  );
};
