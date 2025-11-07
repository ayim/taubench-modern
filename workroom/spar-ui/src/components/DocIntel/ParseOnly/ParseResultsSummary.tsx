import { FC, useMemo } from 'react';
import { Box, Typography, Table, Tooltip } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { IconSparkles2 } from '@sema4ai/icons';
import { ParseResult } from '../shared/types';

/**
 * ParseResultsSummary - Displays a summary view of parse results
 * Shows high-level statistics and structured content including tables
 */

interface ParseResultsSummaryProps {
  parseResult: ParseResult;
}

interface ParsedBlock {
  type: string;
  content: string;
  page?: number;
  tableData?: {
    columns: Array<{ id: string; title: string }>;
    data: Array<Record<string, string>>;
  };
}

const parseTableContent = (
  content: string,
): { columns: Array<{ id: string; title: string }>; data: Array<Record<string, string>> } | null => {
  try {
    // Try to parse HTML table from content
    const parser = new DOMParser();
    const doc = parser.parseFromString(content, 'text/html');
    const table = doc.querySelector('table');

    if (!table) return null;

    const headers = Array.from(table.querySelectorAll('th')).map((th) => th.textContent?.trim() || '');
    const rows = Array.from(table.querySelectorAll('tr')).slice(1); // Skip header row

    if (headers.length === 0) return null;

    const columns = headers.map((header, idx) => ({
      id: `col_${idx}`,
      title: header || `Column ${idx + 1}`,
    }));

    const data = rows.map((row) => {
      const cells = Array.from(row.querySelectorAll('td')).map((td) => td.textContent?.trim() || '');
      return Object.fromEntries(columns.map((col, idx) => [col.id, cells[idx] || '']));
    });

    return { columns, data };
  } catch {
    // Failed to parse table content
    return null;
  }
};

const extractBlocks = (parseResult: ParseResult): ParsedBlock[] => {
  const blocks: ParsedBlock[] = [];
  const chunks = parseResult;

  chunks.forEach((chunk: ParseResult[0]) => {
    const chunkBlocks = chunk.blocks;
    if (chunkBlocks) {
      chunkBlocks.forEach((block) => {
        const blockType = block.type || 'Text';
        const blockContent = block.content;
        const blockPage = block.bbox?.page;

        // Handle Table blocks specially
        if (blockType === 'Table' && blockContent) {
          const tableData = parseTableContent(blockContent);
          if (tableData) {
            blocks.push({
              type: blockType,
              content: blockContent,
              page: blockPage,
              tableData,
            });
          } else {
            // Fallback to raw content if table parsing fails
            blocks.push({
              type: blockType,
              content: blockContent,
              page: blockPage,
            });
          }
        } else if (blockContent && blockContent.trim().length > 0) {
          // Regular content blocks
          blocks.push({
            type: blockType,
            content: blockContent.trim(),
            page: blockPage,
          });
        }
      });
    }
  });

  return blocks;
};

const HoverableBox = styled(Box)`
  transition: background-color 0.2s ease;
  cursor: default;

  &:hover {
    background-color: rgba(0, 0, 0, 0.02);
  }
`;

const BlockRenderer: FC<{ block: ParsedBlock }> = ({ block }) => {
  // Render tables
  if (block.type === 'Table' && block.tableData) {
    const pageInfo = block.page === undefined ? '' : ` (Page ${block.page})`;
    return (
      <Tooltip text={`Table${pageInfo}`}>
        <HoverableBox marginBottom="$32" borderRadius="$4" padding="$8">
          <Table columns={block.tableData.columns} data={block.tableData.data} />
        </HoverableBox>
      </Tooltip>
    );
  }

  // Render other block types with document-like styling
  const getBlockStyle = (type: string) => {
    switch (type) {
      case 'Title':
        return {
          fontSize: '$20',
          fontWeight: 700 as const,
          marginBottom: '$24',
          lineHeight: '1.3',
        };
      case 'Section Header':
        return {
          fontSize: '$18',
          fontWeight: 600 as const,
          marginBottom: '$20',
          lineHeight: '1.4',
        };
      case 'Page Header':
      case 'Page Footer':
        return {
          fontSize: '$11',
          color: 'content.subtle' as const,
          marginBottom: '$16',
          lineHeight: '1.5',
        };
      default:
        return {
          fontSize: '$16',
          marginBottom: '$20',
          lineHeight: '1.6',
        };
    }
  };

  const style = getBlockStyle(block.type);

  // Format tooltip text
  const pageInfo = block.page === undefined ? '' : ` • Page ${block.page}`;
  const tooltipText = `${block.type}${pageInfo}`;

  return (
    <Tooltip text={tooltipText}>
      <HoverableBox marginBottom={style.marginBottom} borderRadius="$4" padding="$8" marginLeft="-$8" marginRight="-$8">
        <Typography
          fontSize={style.fontSize}
          fontWeight={style.fontWeight}
          color={style.color}
          style={{ lineHeight: style.lineHeight, whiteSpace: 'pre-wrap' }}
        >
          {block.content}
        </Typography>
      </HoverableBox>
    </Tooltip>
  );
};

export const ParseResultsSummary: FC<ParseResultsSummaryProps> = ({ parseResult }) => {
  const blocks = useMemo(() => extractBlocks(parseResult), [parseResult]);

  return (
    <Box
      padding="$24"
      display="flex"
      flexDirection="column"
      height="100%"
      overflow="auto"
      style={{
        maxWidth: '900px',
        margin: '0 auto',
      }}
    >
      <Box display="flex" alignItems="center" gap="$8" marginBottom="$12">
        <IconSparkles2 color="content.subtle.light" />
        <Typography fontSize="$12" fontWeight="medium" color="content.subtle.light">
          Parsed fields and tables are inferred below.
        </Typography>
      </Box>
      {/* Structured Content - Document-like rendering */}
      {blocks.length > 0 ? (
        <Box display="flex" flexDirection="column">
          {blocks.map((block) => {
            // Create a unique key based on block content and metadata
            const contentHash = block.content.substring(0, 50).replaceAll(/\s/g, '-');
            const blockKey = `${block.type}-${block.page ?? 'np'}-${contentHash}`;
            return <BlockRenderer key={blockKey} block={block} />;
          })}
        </Box>
      ) : (
        <Box display="flex" alignItems="center" justifyContent="center" height="100%">
          <Typography color="content.subtle">No content to display</Typography>
        </Box>
      )}
    </Box>
  );
};
