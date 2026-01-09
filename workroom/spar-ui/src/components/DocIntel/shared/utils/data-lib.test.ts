import { describe, it, expect } from 'vitest';
import {
  toRenderedParseBlocks,
  toRenderedExtractBlocks,
  parseChunksToThreadJSON,
  type ParseResultChunks,
} from './data-lib';

// ============================================================================
// Test Fixtures
// ============================================================================

const createParseChunk = (
  blocks: Array<{ type?: string; content?: string; bbox?: { page?: number } }>,
): ParseResultChunks[0] =>
  ({
    blocks: blocks.map((b) => ({
      type: b.type || 'Text',
      content: b.content || '',
      bbox: b.bbox,
    })),
  }) as ParseResultChunks[0];

const simpleParseChunks: ParseResultChunks = [
  createParseChunk([
    { type: 'Title', content: 'Invoice #12345' },
    { type: 'Text', content: 'Customer: John Doe', bbox: { page: 1 } },
    { type: 'Text', content: 'Date: 2024-01-15', bbox: { page: 1 } },
  ]),
];

const parseChunksWithTable: ParseResultChunks = [
  createParseChunk([
    { type: 'Title', content: 'Product Catalog' },
    {
      type: 'Table',
      content: `<table>
        <tr><th>SKU</th><th>Name</th><th>Price</th></tr>
        <tr><td>ABC123</td><td>Widget</td><td>$19.99</td></tr>
        <tr><td>DEF456</td><td>Gadget</td><td>$29.99</td></tr>
      </table>`,
      bbox: { page: 1 },
    },
  ]),
];

const parseChunksWithSections: ParseResultChunks = [
  createParseChunk([
    { type: 'Title', content: 'Annual Report' },
    { type: 'Section Header', content: 'Executive Summary' },
    { type: 'Text', content: 'This year was successful.' },
    { type: 'Text', content: 'Revenue grew by 20%.' },
    { type: 'Section Header', content: 'Financial Overview' },
    { type: 'Text', content: 'Total revenue: $1M.' },
  ]),
];

const simpleExtractResult = {
  result: {
    invoice_number: 'INV-001',
    customer_name: 'John Doe',
    total_amount: 150,
  },
  citations: null,
};

const extractResultWithNestedObject = {
  result: {
    merchant_name: 'ACME Corp',
    address: {
      city: 'New York',
      state: 'NY',
      zip: '10001',
    },
    total: 99.99,
  },
  citations: null,
};

const extractResultWithSimpleArray = {
  result: {
    store_name: 'Electronics Store',
    payment: [
      { method: 'Visa', amount: 100, last_four: '1234' },
      { method: 'Cash', amount: 50, last_four: null },
    ],
  },
  citations: null,
};

const extractResultWithTableWrapper = {
  result: {
    receipt_id: 'REC-001',
    tables: [
      {
        table_name: 'line_items',
        rows: [
          { item_code: '123', description: 'Widget', price: 10 },
          { item_code: '456', description: 'Gadget', price: 20 },
          { item_code: '789', description: 'Thingamajig', price: 30 },
        ],
      },
    ],
  },
  citations: null,
};

// ============================================================================
// toRenderedParseBlocks Tests
// ============================================================================

describe('toRenderedParseBlocks', () => {
  it('transforms parse chunks to blocks with correct structure', () => {
    const blocks = toRenderedParseBlocks(simpleParseChunks);

    expect(blocks).toHaveLength(3);
    expect(blocks[0]).toEqual({
      id: 'block-0-0',
      type: 'Title',
      content: 'Invoice #12345',
    });
    expect(blocks[1]).toEqual({
      id: 'block-0-1',
      type: 'Text',
      content: 'Customer: John Doe',
      page: 1,
    });
  });

  it('creates table block preserving raw HTML (DOMParser not available in Node)', () => {
    const blocks = toRenderedParseBlocks(parseChunksWithTable);
    const tableBlock = blocks.find((b) => b.type === 'Table');

    expect(tableBlock?.type).toBe('Table');
    expect(tableBlock?.content).toContain('<table>');
    expect(tableBlock?.content).toContain('SKU');
  });

  it('returns empty array for empty chunks', () => {
    expect(toRenderedParseBlocks([])).toEqual([]);
  });

  it('skips blocks with empty or whitespace content', () => {
    const chunks = [
      createParseChunk([
        { type: 'Text', content: 'Valid' },
        { type: 'Text', content: '' },
        { type: 'Text', content: '   ' },
        { type: 'Text', content: 'Also valid' },
      ]),
    ];

    const blocks = toRenderedParseBlocks(chunks);
    expect(blocks).toHaveLength(2);
    expect(blocks.map((b) => b.content)).toEqual(['Valid', 'Also valid']);
  });

  it('preserves page numbers from bbox', () => {
    const chunks = [
      createParseChunk([
        { type: 'Text', content: 'Page 1', bbox: { page: 1 } },
        { type: 'Text', content: 'Page 2', bbox: { page: 2 } },
        { type: 'Text', content: 'No page' },
      ]),
    ];

    const blocks = toRenderedParseBlocks(chunks);
    expect(blocks.map((b) => b.page)).toEqual([1, 2, undefined]);
  });

  it('handles multiple chunks with unique IDs', () => {
    const chunks = [
      createParseChunk([{ type: 'Title', content: 'Chapter 1' }]),
      createParseChunk([{ type: 'Text', content: 'Content' }]),
    ];

    const blocks = toRenderedParseBlocks(chunks);
    expect(blocks[0].id).toBe('block-0-0');
    expect(blocks[1].id).toBe('block-1-0');
  });
});

// ============================================================================
// toRenderedExtractBlocks Tests
// ============================================================================

describe('toRenderedExtractBlocks', () => {
  it('transforms simple extract result to text blocks with labels', () => {
    const blocks = toRenderedExtractBlocks(simpleExtractResult);

    const invoiceBlock = blocks.find((b) => b.content === 'INV-001');
    expect(invoiceBlock).toEqual({
      id: 'extract-invoice_number',
      type: 'Text',
      content: 'INV-001',
      label: 'invoice number',
      page: undefined,
    });
  });

  it('creates section headers for nested objects', () => {
    const blocks = toRenderedExtractBlocks(extractResultWithNestedObject);

    const sectionHeader = blocks.find((b) => b.type === 'Section Header');
    expect(sectionHeader?.content).toBe('address');

    const cityBlock = blocks.find((b) => b.content === 'New York');
    expect(cityBlock?.label).toBe('city');
  });

  it('renders arrays of objects as tables', () => {
    const blocks = toRenderedExtractBlocks(extractResultWithSimpleArray);
    const tableBlock = blocks.find((b) => b.type === 'Table');

    expect(tableBlock?.tableData?.data).toHaveLength(2);
    expect(tableBlock?.tableData?.columns.map((c) => c.id)).toEqual(
      expect.arrayContaining(['method', 'amount', 'last_four']),
    );
  });

  it('renders table wrapper arrays with section headers and tables', () => {
    const blocks = toRenderedExtractBlocks(extractResultWithTableWrapper);

    const headers = blocks.filter((b) => b.type === 'Section Header').map((b) => b.content);
    expect(headers).toContain('tables');
    expect(headers).toContain('line_items');

    const tableBlock = blocks.find((b) => b.type === 'Table');
    expect(tableBlock?.tableData?.data).toHaveLength(3);
  });

  it.each([
    { result: null, description: 'null' },
    { result: undefined, description: 'undefined' },
  ])('returns empty array for $description result', ({ result }) => {
    expect(toRenderedExtractBlocks({ result, citations: null })).toEqual([]);
  });

  it('handles arrays with optional/undefined fields (isPrimitive fix)', () => {
    const data = {
      result: {
        items: [
          { sku: 'A1', name: 'Alpha', quantity: 1, notes: 'Fragile' },
          { sku: 'B2', name: 'Beta', quantity: 2, notes: undefined },
          { sku: 'C3', name: 'Gamma', quantity: undefined, notes: null },
        ],
      },
      citations: null,
    };

    const blocks = toRenderedExtractBlocks(data);
    const tableBlock = blocks.find((b) => b.type === 'Table');

    expect(tableBlock?.tableData?.data).toHaveLength(3);
    expect(tableBlock?.tableData?.columns.map((c) => c.id)).toEqual(
      expect.arrayContaining(['sku', 'name', 'quantity', 'notes']),
    );
  });

  it('formats field labels by replacing underscores with spaces', () => {
    const blocks = toRenderedExtractBlocks({
      result: { customer_first_name: 'John' },
      citations: null,
    });

    expect(blocks[0].label).toBe('customer first name');
  });

  it('skips empty and whitespace-only string values', () => {
    const blocks = toRenderedExtractBlocks({
      result: { filled: 'value', empty: '', whitespace: '   ' },
      citations: null,
    });

    expect(blocks).toHaveLength(1);
    expect(blocks[0].content).toBe('value');
  });
});

// ============================================================================
// parseChunksToThreadJSON Tests
// ============================================================================

describe('parseChunksToThreadJSON', () => {
  it('extracts title and content from simple document', () => {
    const result = parseChunksToThreadJSON(simpleParseChunks);

    expect(result).toEqual({
      document_title: 'Invoice #12345',
      document_content: 'Customer: John Doe\n\nDate: 2024-01-15',
    });
  });

  it('extracts sections with headers and combined content as document_content', () => {
    const result = parseChunksToThreadJSON(parseChunksWithSections);

    expect(result.document_title).toBe('Annual Report');
    // Sections are now formatted as text in document_content
    expect(result.document_content).toContain('Executive Summary');
    expect(result.document_content).toContain('This year was successful.');
    expect(result.document_content).toContain('Financial Overview');
    expect(result.document_content).toContain('Total revenue: $1M.');
  });

  it('omits tables field when DOMParser unavailable (Node environment)', () => {
    const result = parseChunksToThreadJSON(parseChunksWithTable);

    expect(result.document_title).toBe('Product Catalog');
    expect(result.tables).toBeUndefined();
  });

  it('returns empty object for empty chunks', () => {
    expect(parseChunksToThreadJSON([])).toEqual({});
  });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('Edge Cases', () => {
  it('handles deeply nested extract data', () => {
    const blocks = toRenderedExtractBlocks({
      result: { level1: { level2: { level3: { deep_value: 'Found it!' } } } },
      citations: null,
    });

    expect(blocks.find((b) => b.content === 'Found it!')).toBeDefined();
  });

  it('does not render primitive arrays as tables', () => {
    const blocks = toRenderedExtractBlocks({
      result: { tags: ['red', 'green', 'blue'] },
      citations: null,
    });

    expect(blocks.find((b) => b.type === 'Table')).toBeUndefined();
  });

  it('does not render single-key object arrays as tables', () => {
    const blocks = toRenderedExtractBlocks({
      result: { items: [{ value: 1 }, { value: 2 }] },
      citations: null,
    });

    expect(blocks.find((b) => b.type === 'Table')).toBeUndefined();
  });

  it('handles multiple table wrappers with correct section headers', () => {
    const blocks = toRenderedExtractBlocks({
      result: {
        tables: [
          { table_name: 'products', rows: [{ id: '1', name: 'A', price: 10 }] },
          { table_name: 'categories', rows: [{ id: 'C1', cat: 'Electronics' }] },
        ],
      },
      citations: null,
    });

    const headers = blocks.filter((b) => b.type === 'Section Header').map((b) => b.content);
    expect(headers).toEqual(['tables', 'products', 'categories']);

    const tables = blocks.filter((b) => b.type === 'Table');
    expect(tables).toHaveLength(2);
  });

  it('converts boolean and number values to strings', () => {
    const blocks = toRenderedExtractBlocks({
      result: { active: true, count: 42, rate: 3.14 },
      citations: null,
    });

    expect(blocks.map((b) => b.content)).toEqual(['true', '42', '3.14']);
  });
});

// ============================================================================
// Costco Receipt Scenario (validates isPrimitive fix)
// ============================================================================

describe('Costco Receipt Scenario', () => {
  it('renders table wrapper with optional fields correctly', () => {
    const blocks = toRenderedExtractBlocks({
      result: {
        merchant_name: 'COSTCO WHOLESALE',
        tables: [
          {
            table_name: 'line_items',
            rows: [
              { line_index: 0, item_code: '123', description: 'CHARMIN', price: 22.49, right_flag: 'A' },
              { line_index: 1, left_flag: 'E', item_code: '456', description: 'ORANGES', price: 12.99 },
              { line_index: 2, left_flag: 'E', item_code: '789', description: 'HONEYDEW', price: 3.99 },
            ],
          },
        ],
      },
      citations: null,
    });

    const tableBlock = blocks.find((b) => b.type === 'Table' && b.id.includes('rows-table'));
    expect(tableBlock?.tableData?.data).toHaveLength(3);

    const columnIds = tableBlock?.tableData?.columns.map((c) => c.id) || [];
    expect(columnIds).toEqual(
      expect.arrayContaining(['line_index', 'item_code', 'description', 'price', 'right_flag', 'left_flag']),
    );
  });
});
