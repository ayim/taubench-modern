import { removeCitationFromExtractedData } from './dataTransformations';
import type { ExtractDocumentResponsePayload } from '../store/useDocumentIntelligenceStore';

function runTest(testName: string, testFn: () => void) {
  try {
    testFn();
    // eslint-disable-next-line no-console
    console.log(`✅ ${testName}`);
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error(`❌ ${testName}: ${error}`);
  }
}

// Helper function to create sample citation data
function createSampleCitationData(): ExtractDocumentResponsePayload {
  return {
    result: {},
    citations: {
      invoice_number: {
        bbox: [100, 200, 300, 250],
        content: "INV-12345"
      },
      Invoice_Date: {
        bbox: [100, 300, 200, 350],
        content: "2024-01-15"
      },
      inspection_summary_0: {
        bbox: [100, 400, 500, 450],
        content: "First inspection item"
      },
      inspection_summary_1: {
        bbox: [100, 500, 500, 550],
        content: "Second inspection item"
      },
      nested: {
        field: {
          bbox: [100, 600, 300, 650],
          content: "Nested field content"
        }
      },
      array_field: [
        {
          bbox: [100, 700, 300, 750],
          content: "Array item 1"
        },
        {
          bbox: [100, 800, 300, 850],
          content: "Array item 2"
        }
      ]
    }
  } as ExtractDocumentResponsePayload;
}

// Test exact match
runTest('Exact match removal', () => {
  const data = createSampleCitationData();
  const result = removeCitationFromExtractedData(data, 'invoice_number');

  if (result.citations && 'invoice_number' in result.citations) {
    throw new Error('invoice_number should be removed');
  }

  if (!result.citations || !('Invoice_Date' in result.citations)) {
    throw new Error('Invoice_Date should still be present');
  }
});

// Test case-insensitive match
runTest('Case-insensitive match removal', () => {
  const data = createSampleCitationData();
  const result = removeCitationFromExtractedData(data, 'invoice_date');

  if (result.citations && 'Invoice_Date' in result.citations) {
    throw new Error('Invoice_Date should be removed (case-insensitive match)');
  }

  if (!result.citations || !('invoice_number' in result.citations)) {
    throw new Error('invoice_number should still be present');
  }
});

// Test array index match
runTest('Array index match removal', () => {
  const data = createSampleCitationData();
  const result = removeCitationFromExtractedData(data, 'inspection_summary');

  if (result.citations && ('inspection_summary_0' in result.citations || 'inspection_summary_1' in result.citations)) {
    throw new Error('inspection_summary_0 and inspection_summary_1 should be removed');
  }

  if (!result.citations || !('invoice_number' in result.citations)) {
    throw new Error('invoice_number should still be present');
  }
});

// Test nested field removal
runTest('Nested field removal', () => {
  const data = createSampleCitationData();
  const result = removeCitationFromExtractedData(data, 'nested.field');

  if (result.citations && result.citations.nested && typeof result.citations.nested === 'object' && result.citations.nested !== null && 'field' in result.citations.nested) {
    throw new Error('nested.field should be removed');
  }

  if (!result.citations || !('invoice_number' in result.citations)) {
    throw new Error('invoice_number should still be present');
  }
});

// Test array field removal
runTest('Array field removal', () => {
  const data = createSampleCitationData();
  const result = removeCitationFromExtractedData(data, 'array_field');

  if (result.citations && 'array_field' in result.citations) {
    throw new Error('array_field should be removed');
  }

  if (!result.citations || !('invoice_number' in result.citations)) {
    throw new Error('invoice_number should still be present');
  }
});

// Test non-existent field (should not affect anything)
runTest('Non-existent field removal (no-op)', () => {
  const data = createSampleCitationData();
  const result = removeCitationFromExtractedData(data, 'non_existent_field');

  // All original fields should still be present
  const originalKeys = Object.keys(data.citations || {});
  const resultKeys = Object.keys(result.citations || {});

  if (originalKeys.length !== resultKeys.length) {
    throw new Error('No fields should be removed when targeting non-existent field');
  }
});

// Test empty citations object
runTest('Empty citations object', () => {
  const data = { result: {}, citations: {} } as ExtractDocumentResponsePayload;
  const result = removeCitationFromExtractedData(data, 'any_field');

  if (!result.citations || Object.keys(result.citations).length !== 0) {
    throw new Error('Empty citations should remain empty');
  }
});

// Test null citations
runTest('Null citations', () => {
  const data = { result: {}, citations: null } as ExtractDocumentResponsePayload;
  const result = removeCitationFromExtractedData(data, 'any_field');

  if (result.citations !== null) {
    throw new Error('Null citations should remain null');
  }
});

// eslint-disable-next-line no-console
console.log('\n🎉 All tests completed!');
