/* eslint-disable camelcase */
import { describe, expect, it } from 'vitest';
import {
  getDataConnectionId,
  getQueryParameterValue,
  applyQueryParameterValue,
  applyQueryParameterName,
} from './SemanticDataModels';
import { QueryParameter } from '~/queries/semanticData';
import { SemanticModel } from '~/queries/semanticData';

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
          base_table: { data_connection_id: 'conn-123', table: 'table-1' },
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
          base_table: { table: 'table-1' },
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
          base_table: { table: 'table-1' },
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
          base_table: { data_connection_id: 'conn-456', table: 'table-2' },
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

describe('getQueryParameterValue', () => {
  const createParameter = (overrides: Partial<QueryParameter> & Pick<QueryParameter, 'data_type'>): QueryParameter => ({
    name: 'test_param',
    description: 'Test parameter',
    example_value: undefined,
    ...overrides,
  });

  describe('string type', () => {
    it.each([
      { exampleValue: 'hello', expected: "'hello'" },
      { exampleValue: '', expected: "''" },
      { exampleValue: "it's a test", expected: "'it''s a test'" },
      { exampleValue: "multiple'quotes'here", expected: "'multiple''quotes''here'" },
      { exampleValue: undefined, expected: "''" },
      { exampleValue: null, expected: "''" },
    ])('returns $expected for exampleValue=$exampleValue', ({ exampleValue, expected }) => {
      const param = createParameter({ data_type: 'string', example_value: exampleValue });
      expect(getQueryParameterValue(param)).toBe(expected);
    });
  });

  describe('datetime type', () => {
    it.each([
      { example_value: '2024-01-15', expected: "'2024-01-15'" },
      { example_value: '2024-01-15T10:30:00Z', expected: "'2024-01-15T10:30:00Z'" },
      { example_value: undefined, expected: "''" },
      { example_value: null, expected: "''" },
    ])('returns $expected for example_value=$example_value', ({ example_value, expected }) => {
      const param = createParameter({ data_type: 'datetime', example_value });
      expect(getQueryParameterValue(param)).toBe(expected);
    });
  });

  describe('integer type', () => {
    it.each([
      { example_value: 42, expected: '42' },
      { example_value: 0, expected: '0' },
      { example_value: -100, expected: '-100' },
      { example_value: undefined, expected: '0' },
      { example_value: null, expected: '0' },
    ])('returns $expected for example_value=$example_value', ({ example_value, expected }) => {
      const param = createParameter({ data_type: 'integer', example_value });
      expect(getQueryParameterValue(param)).toBe(expected);
    });
  });

  describe('float type', () => {
    it.each([
      { example_value: 3.14, expected: '3.14' },
      { example_value: 0.0, expected: '0' },
      { example_value: -2.5, expected: '-2.5' },
      { example_value: undefined, expected: '0' },
      { example_value: null, expected: '0' },
    ])('returns $expected for example_value=$example_value', ({ example_value, expected }) => {
      const param = createParameter({ data_type: 'float', example_value });
      expect(getQueryParameterValue(param)).toBe(expected);
    });
  });

  describe('boolean type', () => {
    it.each([
      { example_value: true, expected: 'true' },
      { example_value: false, expected: 'false' },
      { example_value: undefined, expected: 'true' },
      { example_value: null, expected: 'true' },
    ])('returns $expected for example_value=$example_value', ({ example_value, expected }) => {
      const param = createParameter({ data_type: 'boolean', example_value });
      expect(getQueryParameterValue(param)).toBe(expected);
    });
  });
});

describe('applyQueryParameterValue', () => {
  const createParameter = (
    overrides: Partial<QueryParameter> & Pick<QueryParameter, 'name' | 'data_type'>,
  ): QueryParameter => ({
    description: 'Test parameter',
    example_value: undefined,
    ...overrides,
  });

  it('replaces string parameter placeholder with quoted value', () => {
    const query = 'SELECT * FROM users WHERE name = :user_name';
    const param = createParameter({ name: 'user_name', data_type: 'string', example_value: 'John' });

    expect(applyQueryParameterValue(query, param)).toBe("SELECT * FROM users WHERE name = 'John'");
  });

  it('replaces integer parameter placeholder with numeric value', () => {
    const query = 'SELECT * FROM orders WHERE id = :order_id';
    const param = createParameter({ name: 'order_id', data_type: 'integer', example_value: 123 });

    expect(applyQueryParameterValue(query, param)).toBe('SELECT * FROM orders WHERE id = 123');
  });

  it('replaces boolean parameter placeholder with boolean string', () => {
    const query = 'SELECT * FROM users WHERE active = :is_active';
    const param = createParameter({ name: 'is_active', data_type: 'boolean', example_value: false });

    expect(applyQueryParameterValue(query, param)).toBe('SELECT * FROM users WHERE active = false');
  });

  it('replaces datetime parameter placeholder with quoted value', () => {
    const query = 'SELECT * FROM events WHERE date > :start_date';
    const param = createParameter({ name: 'start_date', data_type: 'datetime', example_value: '2024-01-01' });

    expect(applyQueryParameterValue(query, param)).toBe("SELECT * FROM events WHERE date > '2024-01-01'");
  });

  it('replaces only the first occurrence of the parameter', () => {
    const query = 'SELECT * FROM users WHERE name = :name OR alias = :name';
    const param = createParameter({ name: 'name', data_type: 'string', example_value: 'test' });

    expect(applyQueryParameterValue(query, param)).toBe("SELECT * FROM users WHERE name = 'test' OR alias = :name");
  });

  it('leaves query unchanged if parameter not found', () => {
    const query = 'SELECT * FROM users WHERE id = :user_id';
    const param = createParameter({ name: 'other_param', data_type: 'string', example_value: 'value' });

    expect(applyQueryParameterValue(query, param)).toBe('SELECT * FROM users WHERE id = :user_id');
  });
});

describe('applyQueryParameterName', () => {
  const createParameter = (
    overrides: Partial<QueryParameter> & Pick<QueryParameter, 'name' | 'data_type'>,
  ): QueryParameter => ({
    description: 'Test parameter',
    example_value: undefined,
    ...overrides,
  });

  it('replaces string value with parameter placeholder', () => {
    const query = "SELECT * FROM users WHERE name = 'John'";
    const param = createParameter({ name: 'user_name', data_type: 'string', example_value: 'John' });

    expect(applyQueryParameterName(query, param)).toBe('SELECT * FROM users WHERE name = :user_name');
  });

  it('replaces integer value with parameter placeholder', () => {
    const query = 'SELECT * FROM orders WHERE id = 123';
    const param = createParameter({ name: 'order_id', data_type: 'integer', example_value: 123 });

    expect(applyQueryParameterName(query, param)).toBe('SELECT * FROM orders WHERE id = :order_id');
  });

  it('replaces boolean value with parameter placeholder', () => {
    const query = 'SELECT * FROM users WHERE active = false';
    const param = createParameter({ name: 'is_active', data_type: 'boolean', example_value: false });

    expect(applyQueryParameterName(query, param)).toBe('SELECT * FROM users WHERE active = :is_active');
  });

  it('replaces datetime value with parameter placeholder', () => {
    const query = "SELECT * FROM events WHERE date > '2024-01-01'";
    const param = createParameter({ name: 'start_date', data_type: 'datetime', example_value: '2024-01-01' });

    expect(applyQueryParameterName(query, param)).toBe('SELECT * FROM events WHERE date > :start_date');
  });

  it('replaces only the first occurrence of the value', () => {
    const query = "SELECT * FROM users WHERE name = 'test' OR alias = 'test'";
    const param = createParameter({ name: 'name', data_type: 'string', example_value: 'test' });

    expect(applyQueryParameterName(query, param)).toBe("SELECT * FROM users WHERE name = :name OR alias = 'test'");
  });

  it('leaves query unchanged if value not found', () => {
    const query = 'SELECT * FROM users WHERE id = 999';
    const param = createParameter({ name: 'order_id', data_type: 'integer', example_value: 123 });

    expect(applyQueryParameterName(query, param)).toBe('SELECT * FROM users WHERE id = 999');
  });

  it('handles string values with escaped quotes', () => {
    const query = "SELECT * FROM users WHERE name = 'it''s a test'";
    const param = createParameter({ name: 'user_name', data_type: 'string', example_value: "it's a test" });

    expect(applyQueryParameterName(query, param)).toBe('SELECT * FROM users WHERE name = :user_name');
  });
});
