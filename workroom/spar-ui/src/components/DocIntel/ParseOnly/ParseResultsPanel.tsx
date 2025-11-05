import { FC } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { ProcessingLoadingState } from '../shared/components/ProcessingLoadingState';

/**
 * ParseResultsPanel - Display parsed document results
 * Shows the JSON structure of the parsed document in a readable format
 */

interface ParseResultsPanelProps {
  parseResult: Record<string, unknown> | null;
  isLoading: boolean;
  error: string | null;
}

export const ParseResultsPanel: FC<ParseResultsPanelProps> = ({ parseResult, isLoading, error }) => {
  if (isLoading) {
    return (
      <ProcessingLoadingState title="Parsing Document" description="Extracting text and structure from your document" />
    );
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

  return (
    <Box
      padding="$16"
      style={{
        height: '100%',
        overflow: 'auto',
      }}
    >
      <Typography variant="body-medium" fontWeight={600} marginBottom="$12">
        Parse Results
      </Typography>
      <Box
        borderRadius="$4"
        backgroundColor="background.panels"
        padding="$12"
        style={{
          fontFamily: 'monospace',
          fontSize: '12px',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {JSON.stringify(parseResult, null, 2)}
      </Box>
    </Box>
  );
};
