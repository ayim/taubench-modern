import { describe, expect, it } from 'vitest';
import { normalizeSchemaName, isValidSchemaName, buildSchemaFromFormData } from './schemaHelpers';
import { SchemaFormData } from './ModelEdition/components/SchemaForm';
import { SchemaFormItem } from './form';

describe('normalizeSchemaName', () => {
  it('trims leading and trailing whitespace', () => {
    expect(normalizeSchemaName('  my_schema  ')).toBe('my_schema');
  });

  it('replaces spaces with underscores', () => {
    expect(normalizeSchemaName('a  b   c')).toBe('a__b___c');
  });

  it('returns empty string for empty input', () => {
    expect(normalizeSchemaName('')).toBe('');
  });
});

describe('isValidSchemaName', () => {
  it('accepts alphanumeric names', () => {
    expect(isValidSchemaName('schema1')).toBe(true);
  });

  it('accepts names with underscores', () => {
    expect(isValidSchemaName('my_schema_2')).toBe(true);
  });

  it('accepts names with spaces', () => {
    expect(isValidSchemaName('my schema')).toBe(true);
  });

  it('accepts empty string', () => {
    expect(isValidSchemaName('')).toBe(true);
  });

  it('rejects names with special characters', () => {
    expect(isValidSchemaName('schema!')).toBe(false);
    expect(isValidSchemaName('schema@name')).toBe(false);
    expect(isValidSchemaName('schema-name')).toBe(false);
    expect(isValidSchemaName('schema.name')).toBe(false);
  });
});

describe('buildSchemaFromFormData', () => {
  const baseFormData: SchemaFormData = {
    name: 'Test Schema',
    description: '  A test schema  ',
    jsonText: '{"type": "object"}',
    useDocumentExtraction: false,
    systemPrompt: '',
    configurationText: '',
  };

  it('normalizes the name and trims description', () => {
    const result = buildSchemaFromFormData({ formData: baseFormData });
    expect(result.name).toBe('Test_Schema');
    expect(result.description).toBe('A test schema');
  });

  it('parses jsonText into json_schema', () => {
    const result = buildSchemaFromFormData({ formData: baseFormData });
    expect(result.json_schema).toEqual({ type: 'object' });
  });

  it('defaults validations and transformations to empty arrays when no existing schema', () => {
    const result = buildSchemaFromFormData({ formData: baseFormData });
    expect(result.validations).toEqual([]);
    expect(result.transformations).toEqual([]);
  });

  it('preserves validations and transformations from existing schema', () => {
    const existingSchema: SchemaFormItem = {
      name: 'existing',
      description: 'existing',
      json_schema: {},
      validations: [{ name: 'v1', description: 'd1', jq_expression: '.foo' }],
      transformations: [{ target_schema_name: 'target', jq_expression: '.bar' }],
    };
    const result = buildSchemaFromFormData({ formData: baseFormData, existingSchema });
    expect(result.validations).toEqual(existingSchema.validations);
    expect(result.transformations).toEqual(existingSchema.transformations);
  });

  it('sets document_extraction to undefined when useDocumentExtraction is false', () => {
    const result = buildSchemaFromFormData({ formData: baseFormData });
    expect(result.document_extraction).toBeUndefined();
  });

  it('builds document_extraction when useDocumentExtraction is true', () => {
    const formData: SchemaFormData = {
      ...baseFormData,
      useDocumentExtraction: true,
      systemPrompt: '  Extract data  ',
      configurationText: '{"key": "value"}',
    };
    const result = buildSchemaFromFormData({ formData });
    expect(result.document_extraction).toEqual({
      system_prompt: 'Extract data',
      configuration: { key: 'value' },
    });
  });

  it('defaults configuration to empty object when configurationText is empty', () => {
    const formData: SchemaFormData = {
      ...baseFormData,
      useDocumentExtraction: true,
      systemPrompt: 'prompt',
      configurationText: '',
    };
    const result = buildSchemaFromFormData({ formData });
    expect(result.document_extraction).toEqual({
      system_prompt: 'prompt',
      configuration: {},
    });
  });

  it('defaults configuration to empty object when configurationText is whitespace', () => {
    const formData: SchemaFormData = {
      ...baseFormData,
      useDocumentExtraction: true,
      systemPrompt: 'prompt',
      configurationText: '   ',
    };
    const result = buildSchemaFromFormData({ formData });
    expect(result.document_extraction).toEqual({
      system_prompt: 'prompt',
      configuration: {},
    });
  });

  it('throws on invalid JSON in jsonText', () => {
    const formData: SchemaFormData = { ...baseFormData, jsonText: 'not json' };
    expect(() => buildSchemaFromFormData({ formData })).toThrow();
  });

  it('throws on invalid JSON in configurationText', () => {
    const formData: SchemaFormData = {
      ...baseFormData,
      useDocumentExtraction: true,
      systemPrompt: 'prompt',
      configurationText: 'not json',
    };
    expect(() => buildSchemaFromFormData({ formData })).toThrow();
  });
});
