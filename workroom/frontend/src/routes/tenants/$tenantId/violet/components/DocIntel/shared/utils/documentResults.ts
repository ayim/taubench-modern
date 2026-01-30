/**
 * Document results transformation utilities
 * Converts parse/extract data into renderable blocks
 */

import type { ParsedBlock } from '../components/DocumentResultsRenderer';
import type { ParseResult } from '../types';

/**
 * Parse HTML table content into structured data
 */
export const parseTableContent = (
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

/**
 * Transform parse result data into renderable blocks
 */
export const parseResultToBlocks = (parseResult: ParseResult): ParsedBlock[] => {
  const blocks: ParsedBlock[] = [];

  parseResult.forEach((chunk, chunkIndex) => {
    const chunkBlocks = chunk.blocks;
    if (chunkBlocks) {
      chunkBlocks.forEach((block, blockIndex) => {
        const blockType = block.type || 'Text';
        const blockContent = block.content;
        const blockPage = block.bbox?.page;

        // Skip empty content
        if (!blockContent || !blockContent.trim()) {
          return;
        }

        // Generate stable ID for block
        const blockId = `block-${chunkIndex}-${blockIndex}`;

        // Handle Table blocks specially
        if (blockType === 'Table') {
          const tableData = parseTableContent(blockContent);
          if (tableData) {
            blocks.push({
              id: blockId,
              type: blockType,
              content: blockContent,
              page: blockPage,
              tableData,
            });
          } else {
            // Fallback to raw content if table parsing fails
            blocks.push({
              id: blockId,
              type: blockType,
              content: blockContent,
              page: blockPage,
            });
          }
        } else {
          // Regular content blocks
          blocks.push({
            id: blockId,
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
