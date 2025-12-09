import { FC } from 'react';
import { Box, Typography, Table, Tooltip } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { IconSparkles2 } from '@sema4ai/icons';

export interface ParsedBlock {
  id: string;
  type: string;
  content: string;
  label?: string; // Optional label to show above content (for extracted fields)
  page?: number;
  tableData?: {
    columns: Array<{ id: string; title: string }>;
    data: Array<Record<string, string>>;
  };
}

interface DocumentResultsRendererProps {
  blocks: ParsedBlock[];
  selectedBlockId?: string | null;
  onBlockClick?: (blockId: string) => void;
  title?: string;
  subtitle?: string;
}

const HoverableBox = styled(Box)<{ $isSelected?: boolean; $isClickable?: boolean }>`
  transition: all 0.2s ease;
  cursor: ${(props) => (props.$isClickable ? 'pointer' : 'default')};
  background-color: ${(props) => (props.$isSelected ? 'rgba(59, 130, 246, 0.1)' : 'transparent')};
  border-left: ${(props) => (props.$isSelected ? '3px solid rgb(59, 130, 246)' : '3px solid transparent')};

  &:hover {
    background-color: ${(props) => (props.$isSelected ? 'rgba(59, 130, 246, 0.15)' : 'rgba(0, 0, 0, 0.02)')};
  }
`;

const BlockRenderer: FC<{
  block: ParsedBlock;
  isSelected: boolean;
  onClick?: () => void;
}> = ({ block, isSelected, onClick }) => {
  // Render tables
  if (block.type === 'Table' && block.tableData) {
    const pageInfo = block.page === undefined ? '' : ` (Page ${block.page})`;
    return (
      <Tooltip text={`Table${pageInfo}`}>
        <HoverableBox
          $isSelected={isSelected}
          $isClickable={!!onClick}
          marginBottom="$32"
          borderRadius="$4"
          padding="$8"
          onClick={onClick}
        >
          <Table columns={block.tableData.columns} data={block.tableData.data} />
        </HoverableBox>
      </Tooltip>
    );
  }

  // Render section headers (like Reducto's group headers)
  if (block.type === 'Section Header') {
    return (
      <Box marginTop="$32" marginBottom="$16">
        <Typography fontSize="$18" fontWeight="bold" color="content.primary">
          {block.content}
        </Typography>
      </Box>
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
          marginBottom: '$12',
          lineHeight: '1.6',
        };
    }
  };

  const style = getBlockStyle(block.type);

  // Format tooltip text
  const pageInfo = block.page === undefined ? '' : ` • Page ${block.page}`;
  const tooltipText = block.label ? `${block.label}${pageInfo}` : `${block.type}${pageInfo}`;

  return (
    <Tooltip text={tooltipText}>
      <HoverableBox
        $isSelected={isSelected}
        $isClickable={!!onClick}
        marginBottom={style.marginBottom}
        borderRadius="$4"
        padding="$8"
        marginLeft="-$8"
        marginRight="-$8"
        onClick={onClick}
      >
        {block.label && (
          <Typography fontSize="$12" color="content.subtle" marginBottom="$4">
            {block.label}
          </Typography>
        )}
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

export const DocumentResultsRenderer: FC<DocumentResultsRendererProps> = ({
  blocks,
  selectedBlockId,
  onBlockClick,
  title = 'Parsed fields and tables are inferred below.',
  subtitle,
}) => {
  return (
    <Box padding="$24" display="flex" flexDirection="column" height="100%" overflow="auto">
      <Box display="flex" alignItems="center" gap="$8" marginBottom="$12">
        <IconSparkles2 color="content.subtle.light" />
        <Typography fontSize="$12" fontWeight="medium" color="content.subtle.light">
          {title}
        </Typography>
      </Box>
      {subtitle && (
        <Typography fontSize="$12" color="content.subtle" marginBottom="$16">
          {subtitle}
        </Typography>
      )}
      {/* Structured Content - Document-like rendering */}
      {blocks.length > 0 ? (
        <Box display="flex" flexDirection="column">
          {blocks.map((block) => (
            <BlockRenderer
              key={block.id}
              block={block}
              isSelected={block.id === selectedBlockId}
              onClick={onBlockClick ? () => onBlockClick(block.id) : undefined}
            />
          ))}
        </Box>
      ) : (
        <Box display="flex" alignItems="center" justifyContent="center" height="100%">
          <Typography color="content.subtle">No content to display</Typography>
        </Box>
      )}
    </Box>
  );
};
