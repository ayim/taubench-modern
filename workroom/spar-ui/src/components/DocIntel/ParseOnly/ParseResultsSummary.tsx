import { FC, useMemo } from 'react';
import { DocumentResultsRenderer } from '../shared/components/DocumentResultsRenderer';
import { parseResultToBlocks } from '../shared/utils/documentResults';
import { ParseResult } from '../shared/types';

/**
 * ParseResultsSummary - Displays a summary view of parse results
 * Shows high-level statistics and structured content including tables
 */

interface ParseResultsSummaryProps {
  parseResult: ParseResult;
}

export const ParseResultsSummary: FC<ParseResultsSummaryProps> = ({ parseResult }) => {
  const blocks = useMemo(() => parseResultToBlocks(parseResult), [parseResult]);

  return <DocumentResultsRenderer blocks={blocks} />;
};
