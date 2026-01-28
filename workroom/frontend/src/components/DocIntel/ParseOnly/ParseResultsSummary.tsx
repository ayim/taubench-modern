import { FC, useMemo } from 'react';
import { DocumentResultsRenderer } from '../shared/components/DocumentResultsRenderer';
import { toRenderedParseBlocks, type ParseResultChunks } from '../shared/utils/data-lib';

/**
 * ParseResultsSummary - Displays a summary view of parse results
 * Shows high-level statistics and structured content including tables
 */

export const ParseResultsSummary: FC<{ parseResult: ParseResultChunks }> = ({ parseResult }) => {
  const blocks = useMemo(() => toRenderedParseBlocks(parseResult), [parseResult]);

  return <DocumentResultsRenderer blocks={blocks} />;
};
