import { describe, expect, it } from 'vitest';
import { removeCitationFromExtractedData } from './dataTransformations';
import type { ExtractDocumentResponsePayload } from '../store/useDocumentIntelligenceStore';

const createSampleCitationData = (): ExtractDocumentResponsePayload => {
  return {
    result: {},
    citations: {
      invoice_number: {
        bbox: [100, 200, 300, 250],
        content: 'INV-12345',
      },
      Invoice_Date: {
        bbox: [100, 300, 200, 350],
        content: '2024-01-15',
      },
      inspection_summary_0: {
        bbox: [100, 400, 500, 450],
        content: 'First inspection item',
      },
      inspection_summary_1: {
        bbox: [100, 500, 500, 550],
        content: 'Second inspection item',
      },
      nested: {
        field: {
          bbox: [100, 600, 300, 650],
          content: 'Nested field content',
        },
      },
      array_field: [
        {
          bbox: [100, 700, 300, 750],
          content: 'Array item 1',
        },
        {
          bbox: [100, 800, 300, 850],
          content: 'Array item 2',
        },
      ],
    },
  } as unknown as ExtractDocumentResponsePayload;
};

describe('removeCitationFromExtractedData', () => {
  it('removes exact match', () => {
    const data = createSampleCitationData();
    const result = removeCitationFromExtractedData(data, 'invoice_number');

    expect(result.citations).not.toHaveProperty('invoice_number');
    expect(result.citations).toHaveProperty('Invoice_Date');
  });

  it('removes case-insensitive match', () => {
    const data = createSampleCitationData();
    const result = removeCitationFromExtractedData(data, 'invoice_date');

    expect(result.citations).not.toHaveProperty('Invoice_Date');
    expect(result.citations).toHaveProperty('invoice_number');
  });

  it('removes array index match', () => {
    const data = createSampleCitationData();
    const result = removeCitationFromExtractedData(data, 'inspection_summary');

    expect(result.citations).not.toHaveProperty('inspection_summary_0');
    expect(result.citations).not.toHaveProperty('inspection_summary_1');
    expect(result.citations).toHaveProperty('invoice_number');
  });

  it('removes nested field', () => {
    const data = createSampleCitationData();
    const result = removeCitationFromExtractedData(data, 'nested.field');

    const nestedCitations = result.citations?.nested;
    const hasNestedField =
      nestedCitations && typeof nestedCitations === 'object' && nestedCitations !== null && 'field' in nestedCitations;

    expect(hasNestedField).toBe(false);
    expect(result.citations).toHaveProperty('invoice_number');
  });

  it('removes array field', () => {
    const data = createSampleCitationData();
    const result = removeCitationFromExtractedData(data, 'array_field');

    expect(result.citations).not.toHaveProperty('array_field');
    expect(result.citations).toHaveProperty('invoice_number');
  });

  it('does not affect non-existent field', () => {
    const data = createSampleCitationData();
    const result = removeCitationFromExtractedData(data, 'non_existent_field');

    const originalKeys = Object.keys(data.citations ?? {});
    const resultKeys = Object.keys(result.citations ?? {});

    expect(resultKeys.length).toBe(originalKeys.length);
  });

  it('handles empty citations object', () => {
    const data = { result: {}, citations: {} } as ExtractDocumentResponsePayload;
    const result = removeCitationFromExtractedData(data, 'any_field');

    expect(result.citations).toEqual({});
  });

  it('handles null citations', () => {
    const data = { result: {}, citations: null } as ExtractDocumentResponsePayload;
    const result = removeCitationFromExtractedData(data, 'any_field');

    expect(result.citations).toBeNull();
  });
});
