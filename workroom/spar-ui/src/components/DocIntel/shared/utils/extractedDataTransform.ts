/**
 * Transform extracted data (with citations) into renderable blocks
 * for the DocumentResultsRenderer component
 */

import type { ParsedBlock } from '../components/DocumentResultsRenderer';

interface Citation {
  bbox?: {
    page?: number;
  };
}

type ExtractedValue = unknown;

interface ExtractedDataResponse {
  result?: Record<string, unknown> | null;
  citations?: Record<string, unknown> | null;
  [key: string]: unknown; // Allow additional properties
}

/**
 * Get page number from citations array
 */
const getPageFromCitations = (citations: unknown): number | undefined => {
  if (Array.isArray(citations) && citations.length > 0) {
    const firstCitation = citations[0] as Citation;
    return firstCitation.bbox?.page;
  }
  return undefined;
};

/**
 * Get page number from array/table citations (uses first item's citation)
 */
const getPageFromArrayCitations = (citations: unknown): number | undefined => {
  if (Array.isArray(citations) && citations.length > 0) {
    // For array data, try to get page from first item's citations
    const firstItemCitations = citations[0];
    if (firstItemCitations && typeof firstItemCitations === 'object') {
      // Citations might be nested - look for any citation with bbox.page
      const values = Object.values(firstItemCitations as Record<string, unknown>);
      const foundPage = values.map((val) => getPageFromCitations(val)).find((page) => page !== undefined);
      if (foundPage !== undefined) return foundPage;
    }
    return getPageFromCitations(firstItemCitations);
  }
  return undefined;
};

/**
 * Format field path for display as a label
 * e.g., "company.name" → "name"
 * e.g., "inspection_items[0].component_name" → "component_name"
 */
const formatFieldLabel = (path: string): string => {
  // Get the last segment of the path
  const parts = path.split('.');
  const lastPart = parts[parts.length - 1];

  // Remove array indices
  const withoutBrackets = lastPart.replace(/\[\d+\]/g, '');

  // Convert snake_case to lowercase with spaces
  return withoutBrackets.replace(/_/g, ' ').toLowerCase();
};

/**
 * Format section header
 * e.g., "company" → "company"
 * e.g., "inspection_items" → "inspection items"
 */
const formatSectionHeader = (key: string): string => {
  return key.replace(/_/g, ' ').toLowerCase();
};

/**
 * Check if a value is a primitive (string, number, boolean, null)
 */
const isPrimitive = (value: unknown): boolean => {
  return value === null || ['string', 'number', 'boolean'].includes(typeof value);
};

/**
 * Check if an array should be rendered as a table
 * Returns true if all items are objects with primitive values (allows optional/sparse fields)
 */
const shouldRenderAsTable = (arr: unknown[]): boolean => {
  if (arr.length === 0) return false;

  // Check if all items are objects (not primitives or arrays)
  const allObjects = arr.every((item) => item !== null && typeof item === 'object' && !Array.isArray(item));

  if (!allObjects) return false;

  // Get keys from first object - require at least 2 keys to be table-worthy
  const firstKeys = Object.keys(arr[0] as Record<string, unknown>);
  if (firstKeys.length < 2) return false;

  // Check that values are primitives - reject if any item has nested objects/arrays
  // This prevents complex structures like transaction_details from being rendered as tables
  const allValuesArePrimitive = arr.every((item) => {
    const obj = item as Record<string, unknown>;
    return Object.values(obj).every(isPrimitive);
  });

  if (!allValuesArePrimitive) return false;

  return true;
};

type TableWrapperItem = { table_name?: string; rows: unknown[] };

/**
 * Check if an array is a "table wrapper" structure
 * e.g., [{ table_name: "...", rows: [...] }] where rows contains the actual table data
 *
 * Without this, we'd render "table_name" and "rows" as columns instead of the actual row data.
 */
const isTableWrapperArray = (arr: unknown[]): boolean => {
  if (arr.length === 0) return false;

  // Check if all items are objects with a 'rows' property that is an array
  return arr.every((item) => {
    if (item === null || typeof item !== 'object' || Array.isArray(item)) return false;
    const obj = item as Record<string, unknown>;
    return Array.isArray(obj.rows) && shouldRenderAsTable(obj.rows as unknown[]);
  });
};

/**
 * Returns typed table wrapper array, or empty array if not valid.
 * Keeps casting in one place.
 */
const getParsedTableWrapperArray = (arr: unknown[]): TableWrapperItem[] => {
  if (!isTableWrapperArray(arr)) return [];
  return arr as TableWrapperItem[];
};

/**
 * Convert a value to a string suitable for table cell display
 */
const valueToString = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'object') {
    // For objects/arrays, use JSON.stringify for readable output
    return JSON.stringify(value);
  }
  return String(value);
};

/**
 * Convert array of objects to table format
 * Uses union of all keys across all items to handle optional/sparse fields
 */
const arrayToTableData = (
  arr: unknown[],
): { columns: Array<{ id: string; title: string }>; data: Array<Record<string, string>> } => {
  if (arr.length === 0) {
    return { columns: [], data: [] };
  }

  // Collect ALL keys from ALL items (union) to handle optional/sparse fields
  const allKeysSet = new Set<string>();
  arr.forEach((item) => {
    Object.keys(item as Record<string, unknown>).forEach((key) => allKeysSet.add(key));
  });
  const keys = Array.from(allKeysSet);

  // Create columns with formatted titles
  const columns = keys.map((key) => ({
    id: key,
    title: formatFieldLabel(key),
  }));

  // Create data rows - missing keys become empty strings via valueToString
  const data = arr.map((item) => {
    const row: Record<string, string> = {};
    keys.forEach((key) => {
      const value = (item as Record<string, unknown>)[key];
      row[key] = valueToString(value);
    });
    return row;
  });

  return { columns, data };
};

/**
 * Recursively flatten extracted data into grouped blocks
 */
const flattenExtractedData = (
  result: ExtractedValue,
  citations: ExtractedValue | undefined,
  path: string,
  blocks: ParsedBlock[],
  depth: number = 0,
): void => {
  // Skip null/undefined values
  if (result === null || result === undefined) {
    return;
  }

  // Handle arrays
  if (Array.isArray(result)) {
    // Handle table wrapper arrays (e.g., [{ table_name: "...", rows: [...] }])
    // Render each item's 'rows' as a table with 'table_name' as header
    const tableWrappers = getParsedTableWrapperArray(result);
    if (tableWrappers.length > 0) {
      const citationsArr = Array.isArray(citations) ? citations : [];
      tableWrappers.forEach(({ table_name: tableName, rows }, index) => {
        const itemPath = `${path}[${index}]`;
        const itemCitations = citationsArr[index] as Record<string, unknown> | undefined;
        const rowsCitations = itemCitations?.rows;
        const page = getPageFromArrayCitations(rowsCitations);

        // Add table name as section header if present
        if (tableName) {
          const sectionBlockId = `extract-${itemPath}-section`;
          blocks.push({
            id: sectionBlockId,
            type: 'Section Header',
            content: tableName,
            page,
          });
        }

        // Render the actual rows as a table
        const blockId = `extract-${itemPath}.rows-table`;
        const tableData = arrayToTableData(rows);

        blocks.push({
          id: blockId,
          type: 'Table',
          content: '', // Not used for tables
          tableData,
          page,
        });
      });
      return;
    }

    // Check if this array should be rendered as a table
    if (shouldRenderAsTable(result)) {
      const blockId = `extract-${path}-table`;
      const tableData = arrayToTableData(result);
      const page = getPageFromArrayCitations(citations);

      blocks.push({
        id: blockId,
        type: 'Table',
        content: '', // Not used for tables
        tableData,
        page,
      });
      return;
    }

    // Otherwise, render as individual items
    result.forEach((item, index) => {
      const itemPath = `${path}[${index}]`;
      const itemCitations = Array.isArray(citations) ? citations[index] : undefined;

      flattenExtractedData(item, itemCitations, itemPath, blocks, depth + 1);
    });
    return;
  }

  // Handle objects (nested structures)
  if (typeof result === 'object') {
    const citationsObj =
      typeof citations === 'object' && !Array.isArray(citations) ? (citations as Record<string, unknown>) : undefined;

    Object.entries(result).forEach(([key, value]) => {
      const fieldPath = path ? `${path}.${key}` : key;
      const fieldCitations = citationsObj ? citationsObj[key] : undefined;

      // Only add section headers at root level (depth 0) for objects/arrays
      if (!isPrimitive(value) && depth === 0) {
        const sectionBlockId = `extract-${fieldPath}-section`;
        blocks.push({
          id: sectionBlockId,
          type: 'Section Header',
          content: formatSectionHeader(key),
          page: undefined,
        });
      }

      flattenExtractedData(value, fieldCitations, fieldPath, blocks, depth + 1);
    });
    return;
  }

  // Handle primitive values (string, number, boolean)
  const blockId = `extract-${path}`;
  const page = getPageFromCitations(citations);
  const displayValue = String(result);

  // Skip empty strings
  if (displayValue.trim().length === 0) {
    return;
  }

  // Add label for field identification
  const label = formatFieldLabel(path);

  blocks.push({
    id: blockId,
    type: 'Text',
    content: displayValue,
    label,
    page,
  });
};

/**
 * Transform extracted data response into blocks for rendering
 */
export const extractedDataToBlocks = (extractedData: ExtractedDataResponse): ParsedBlock[] => {
  const blocks: ParsedBlock[] = [];

  if (!extractedData?.result) {
    return blocks;
  }

  flattenExtractedData(extractedData.result, extractedData.citations, '', blocks, 0);

  return blocks;
};
