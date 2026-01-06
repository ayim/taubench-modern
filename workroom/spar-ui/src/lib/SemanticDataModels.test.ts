import { describe, expect, it } from 'vitest';
import { getDataConnectionId } from './SemanticDataModels';
import { SemanticModel } from '../queries';

describe('getDataConnectionId', () => {
  it('returns data connection ID from first table with one', () => {
    const model: SemanticModel = {
      id: 'model-1',
      name: 'Test Model',
      description: '',
      tables: [
        {
          id: 'table-1',
          name: 'Table 1',
          description: '',
          base_table: { data_connection_id: 'conn-123' },
          dimensions: [],
          time_dimensions: [],
          facts: [],
          metrics: [],
          errors: [],
        },
      ],
      verified_queries: [],
      errors: [],
    };

    expect(getDataConnectionId(model)).toBe('conn-123');
  });

  it('returns undefined when no tables have data connection ID', () => {
    const model: SemanticModel = {
      id: 'model-1',
      name: 'Test Model',
      description: '',
      tables: [
        {
          id: 'table-1',
          name: 'Table 1',
          description: '',
          base_table: {},
          dimensions: [],
          time_dimensions: [],
          facts: [],
          metrics: [],
          errors: [],
        },
      ],
      verified_queries: [],
      errors: [],
    };

    expect(getDataConnectionId(model)).toBeUndefined();
  });

  it('returns undefined for empty tables array', () => {
    const model: SemanticModel = {
      id: 'model-1',
      name: 'Test Model',
      description: '',
      tables: [],
      verified_queries: [],
      errors: [],
    };

    expect(getDataConnectionId(model)).toBeUndefined();
  });

  it('skips tables without data connection ID', () => {
    const model: SemanticModel = {
      id: 'model-1',
      name: 'Test Model',
      description: '',
      tables: [
        {
          id: 'table-1',
          name: 'Table 1',
          description: '',
          base_table: {},
          dimensions: [],
          time_dimensions: [],
          facts: [],
          metrics: [],
          errors: [],
        },
        {
          id: 'table-2',
          name: 'Table 2',
          description: '',
          base_table: { data_connection_id: 'conn-456' },
          dimensions: [],
          time_dimensions: [],
          facts: [],
          metrics: [],
          errors: [],
        },
      ],
      verified_queries: [],
      errors: [],
    };

    expect(getDataConnectionId(model)).toBe('conn-456');
  });
});
