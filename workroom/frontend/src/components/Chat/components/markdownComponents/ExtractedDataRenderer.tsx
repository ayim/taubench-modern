import { FC, useMemo } from 'react';
import { Box, Typography, Table } from '@sema4ai/components';
import { toRenderedExtractBlocks, type ParsedBlock } from '../../../DocIntel/shared/utils/data-lib';

/**
 * Renders a single ParsedBlock based on its type
 */
const BlockRenderer: FC<{ block: ParsedBlock }> = ({ block }) => {
  // Render tables
  if (block.type === 'Table' && block.tableData) {
    return (
      <Box marginBottom="$16">
        <Table columns={block.tableData.columns} data={block.tableData.data} />
      </Box>
    );
  }

  // Render section headers
  if (block.type === 'Section Header') {
    return (
      <Box marginTop="$16" marginBottom="$8">
        <Typography fontSize="$16" fontWeight="bold" color="content.primary">
          {block.content}
        </Typography>
      </Box>
    );
  }

  // Render text/primitive values with optional label
  return (
    <Box marginBottom="$8">
      {block.label && (
        <Typography fontSize="$12" color="content.subtle" marginBottom="$4">
          {block.label}
        </Typography>
      )}
      <Typography fontSize="$14" style={{ whiteSpace: 'pre-wrap' }}>
        {block.content}
      </Typography>
    </Box>
  );
};

export const ExtractedDataRenderer: FC<{ data: unknown }> = ({ data }) => {
  // Transform raw data to ParsedBlock[] using the same logic as Results panel
  const blocks = useMemo(() => {
    // Wrap data in SimpleExtractResponse shape (citations not available in thread)
    return toRenderedExtractBlocks({ results: data, citations: null });
  }, [data]);

  if (blocks.length === 0) {
    return (
      <Box padding="$8">
        <Typography color="content.subtle">No data to display</Typography>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column">
      {blocks.map((block) => (
        <BlockRenderer key={block.id} block={block} />
      ))}
    </Box>
  );
};
