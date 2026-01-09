/**
 * Data Transformation Library
 *
 * A self-contained library for transforming DocIntel results (parse/extract)
 * into renderable blocks and thread-friendly formats.
 *
 * Dependencies:
 *   - zod: ^3.24.2
 */

import { z } from 'zod';
import type { ServerResponse } from '@sema4ai/agent-server-interface';

export const TableDataSchema = z.object({
  columns: z.array(z.object({ id: z.string(), title: z.string() })),
  data: z.array(z.record(z.string(), z.string())),
});

export const ParsedBlockSchema = z.object({
  id: z.string(),
  type: z.string(),
  content: z.string(),
  label: z.string().optional(),
  page: z.number().optional(),
  tableData: TableDataSchema.optional(),
});

export type TableData = z.infer<typeof TableDataSchema>;
export type ParsedBlock = z.infer<typeof ParsedBlockSchema>;

/** Parse result chunks from the document-intelligence API */
export type ParseResultChunks = ServerResponse<
  'post',
  '/api/v2/document-intelligence/documents/parse'
>['result']['chunks'];
export type ExtractResponse = ServerResponse<'post', '/api/v2/document-intelligence/documents/extract'>;

interface Citation {
  bbox?: { page?: number };
}

export interface JSONParseResult {
  document_title?: string;
  document_content?: string;
  tables?: Array<Record<string, string>[]>;
}

type TableWrapperItem = { table_name?: string; rows: unknown[] };

const isPrimitive = (value: unknown): boolean => {
  // Use == null to check for both null and undefined
  return value == null || ['string', 'number', 'boolean'].includes(typeof value);
};

const isPlainObject = (value: unknown): value is Record<string, unknown> => {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
};

const valueToString = (value: unknown): string => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const formatFieldLabel = (path: string): string => {
  const parts = path.split('.');
  const lastPart = parts[parts.length - 1];
  const withoutBrackets = lastPart.replace(/\[\d+\]/g, '');
  return withoutBrackets.replace(/_/g, ' ').toLowerCase();
};

const formatSectionHeader = (key: string): string => {
  return key.replace(/_/g, ' ').toLowerCase();
};

const parseHtmlTable = (content: string): TableData | null => {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(content, 'text/html');
    const table = doc.querySelector('table');

    if (!table) return null;

    const headers = Array.from(table.querySelectorAll('th')).map((th) => th.textContent?.trim() || '');
    const rows = Array.from(table.querySelectorAll('tr')).slice(1);

    if (headers.length === 0) return null;

    // Get first data row to fill in empty headers
    const firstDataRow = rows[0];
    const firstRowCells = firstDataRow
      ? Array.from(firstDataRow.querySelectorAll('td')).map((td) => td.textContent?.trim() || '')
      : [];

    // Track if we used first row to fill any empty headers
    const usedFirstRowForHeaders = headers.some((h, i) => !h && firstRowCells[i]);

    const columns = headers.map((header, idx) => ({
      id: `col_${idx}`,
      // Use header if present, otherwise try first data row, otherwise fall back to "Column N"
      title: header || firstRowCells[idx] || `Column ${idx + 1}`,
    }));

    // Skip first row if it was used to fill headers
    const dataRows = usedFirstRowForHeaders ? rows.slice(1) : rows;

    const data = dataRows.map((row) => {
      const cells = Array.from(row.querySelectorAll('td')).map((td) => td.textContent?.trim() || '');
      return Object.fromEntries(columns.map((col, idx) => [col.id, cells[idx] || '']));
    });

    return { columns, data };
  } catch {
    return null;
  }
};

const shouldRenderAsTable = (arr: unknown[]): boolean => {
  if (arr.length === 0) return false;

  const allObjects = arr.every(isPlainObject);
  if (!allObjects) return false;

  const firstKeys = Object.keys(arr[0]);
  if (firstKeys.length < 2) return false;

  const allValuesArePrimitive = arr.every((item) => {
    return Object.values(item).every(isPrimitive);
  });

  return allValuesArePrimitive;
};

const arrayToTableData = (arr: unknown[]): TableData => {
  const objects = arr.filter(isPlainObject);
  if (objects.length === 0) return { columns: [], data: [] };

  const allKeysSet = new Set<string>();
  objects.forEach((item) => {
    Object.keys(item).forEach((key) => allKeysSet.add(key));
  });
  const keys = Array.from(allKeysSet);

  const columns = keys.map((key) => ({
    id: key,
    title: formatFieldLabel(key),
  }));

  const data = objects.map((item) => {
    const row: Record<string, string> = {};
    keys.forEach((key) => {
      row[key] = valueToString(item[key]);
    });
    return row;
  });

  return { columns, data };
};

const getPageFromCitations = (citations: unknown): number | undefined => {
  if (Array.isArray(citations) && citations.length > 0) {
    const firstCitation = citations[0] as Citation;
    return firstCitation.bbox?.page;
  }
  return undefined;
};

const getPageFromArrayCitations = (citations: unknown): number | undefined => {
  if (Array.isArray(citations) && citations.length > 0) {
    const firstItemCitations = citations[0];
    if (firstItemCitations && typeof firstItemCitations === 'object') {
      const values = Object.values(firstItemCitations as Record<string, unknown>);
      const foundPage = values.map((val) => getPageFromCitations(val)).find((page) => page !== undefined);
      if (foundPage !== undefined) return foundPage;
    }
    return getPageFromCitations(firstItemCitations);
  }
  return undefined;
};

const isTableWrapperArray = (arr: unknown[]): boolean => {
  if (arr.length === 0) return false;
  return arr.every((item) => {
    if (!isPlainObject(item)) return false;
    return Array.isArray(item.rows) && shouldRenderAsTable(item.rows as unknown[]);
  });
};

const getParsedTableWrapperArray = (arr: unknown[]): TableWrapperItem[] => {
  if (!isTableWrapperArray(arr)) return [];
  return arr as TableWrapperItem[];
};

const flattenExtractedData = (
  result: unknown,
  citations: unknown,
  path: string,
  blocks: ParsedBlock[],
  depth: number = 0,
): void => {
  if (result === null || result === undefined) return;

  if (Array.isArray(result)) {
    const tableWrappers = getParsedTableWrapperArray(result);
    if (tableWrappers.length > 0) {
      const citationsArr = Array.isArray(citations) ? citations : [];
      tableWrappers.forEach(({ table_name: tableName, rows }, index) => {
        const itemPath = `${path}[${index}]`;
        const itemCitations = citationsArr[index] as Record<string, unknown> | undefined;
        const page = getPageFromArrayCitations(itemCitations?.rows);

        if (tableName) {
          blocks.push({
            id: `extract-${itemPath}-section`,
            type: 'Section Header',
            content: tableName,
            page,
          });
        }

        blocks.push({
          id: `extract-${itemPath}.rows-table`,
          type: 'Table',
          content: '',
          tableData: arrayToTableData(rows),
          page,
        });
      });
      return;
    }

    if (shouldRenderAsTable(result)) {
      blocks.push({
        id: `extract-${path}-table`,
        type: 'Table',
        content: '',
        tableData: arrayToTableData(result),
        page: getPageFromArrayCitations(citations),
      });
      return;
    }

    result.forEach((item, index) => {
      const itemCitations = Array.isArray(citations) ? citations[index] : undefined;
      flattenExtractedData(item, itemCitations, `${path}[${index}]`, blocks, depth + 1);
    });
    return;
  }

  if (isPlainObject(result)) {
    const citationsObj = isPlainObject(citations) ? citations : undefined;

    Object.entries(result).forEach(([key, value]) => {
      const fieldPath = path ? `${path}.${key}` : key;
      const fieldCitations = citationsObj ? citationsObj[key] : undefined;

      if (!isPrimitive(value) && depth === 0) {
        blocks.push({
          id: `extract-${fieldPath}-section`,
          type: 'Section Header',
          content: formatSectionHeader(key),
          page: undefined,
        });
      }

      flattenExtractedData(value, fieldCitations, fieldPath, blocks, depth + 1);
    });
    return;
  }

  const displayValue = String(result);
  if (!displayValue.trim()) return;

  blocks.push({
    id: `extract-${path}`,
    type: 'Text',
    content: displayValue,
    label: formatFieldLabel(path),
    page: getPageFromCitations(citations),
  });
};

/**
 * Transform parsed blocks into JSON format.
 * Strips IDs, page numbers, and restructures for clarity.
 */
const toJSONParseResult = (blocks: ParsedBlock[]): JSONParseResult => {
  const result: JSONParseResult = {};
  const textBlocks: string[] = [];
  const tables: Array<Record<string, string>[]> = [];
  const sections: Array<{ header: string; content: string[] }> = [];

  let currentSection: { header: string; content: string[] } | null = null;

  blocks.forEach((block) => {
    switch (block.type) {
      case 'Title':
        result.document_title = block.content;
        break;
      case 'Section Header':
        if (currentSection) sections.push(currentSection);
        currentSection = { header: block.content, content: [] };
        break;
      case 'Table':
        if (block.tableData) {
          // Create a mapping from column id to title
          const idToTitle = Object.fromEntries(block.tableData.columns.map((c) => [c.id, c.title]));

          // Transform data to use titles as keys instead of ids
          const transformedData = block.tableData.data.map((row) =>
            Object.fromEntries(Object.entries(row).map(([id, value]) => [idToTitle[id] ?? id, value])),
          );

          tables.push(transformedData);
        }
        break;
      default:
        if (currentSection) {
          currentSection.content.push(block.content);
        } else {
          textBlocks.push(block.content);
        }
    }
  });

  // Push final section
  if (currentSection) sections.push(currentSection);

  // Build clean output - only include non empty fields
  if (textBlocks.length > 0) result.document_content = textBlocks.join('\n\n');
  if (tables.length > 0) result.tables = tables;

  // Format sections as text and append to document_content
  if (sections.length > 0) {
    const sectionsText = sections
      .map((s) => {
        const content = s.content.join('\n');
        return content ? `${s.header}\n${content}` : s.header;
      })
      .join('\n\n');
    result.document_content = result.document_content ? `${result.document_content}\n\n${sectionsText}` : sectionsText;
  }

  return result;
};

/**
 * Transform parse chunks into renderable blocks for UI display.
 */
export const toRenderedParseBlocks = (chunks: ParseResultChunks): ParsedBlock[] => {
  const blocks: ParsedBlock[] = [];

  chunks.forEach((chunk, chunkIndex) => {
    const chunkBlocks = chunk.blocks;
    if (!chunkBlocks) return;

    chunkBlocks.forEach((block, blockIndex) => {
      const blockType = block.type || 'Text';
      const blockContent = block.content;
      const blockPage = block.bbox?.page;

      // Skip empty content
      if (!blockContent?.trim()) return;

      const blockId = `block-${chunkIndex}-${blockIndex}`;

      // Handle Table blocks specially - parse HTML to structured data
      if (blockType === 'Table') {
        const tableData = parseHtmlTable(blockContent);
        blocks.push({
          id: blockId,
          type: blockType,
          content: blockContent,
          page: blockPage,
          ...(tableData && { tableData }),
        });
      } else {
        blocks.push({
          id: blockId,
          type: blockType,
          content: blockContent.trim(),
          page: blockPage,
        });
      }
    });
  });

  return blocks;
};

/**
 * Transform parse chunks directly to thread-friendly JSON format.
 * Convenience function that combines toRenderedParseBlocks + toJSONParseResult.
 */
export const parseChunksToThreadJSON = (chunks: ParseResultChunks): JSONParseResult => {
  const blocks = toRenderedParseBlocks(chunks);
  return toJSONParseResult(blocks);
};

/**
 * Transform extracted data into renderable blocks for UI display.
 */
export const toRenderedExtractBlocks = (extractedData: { result: unknown; citations?: unknown }): ParsedBlock[] => {
  const blocks: ParsedBlock[] = [];
  if (!extractedData?.result) {
    return blocks;
  }
  flattenExtractedData(extractedData.result, extractedData.citations, '', blocks, 0);
  return blocks;
};
