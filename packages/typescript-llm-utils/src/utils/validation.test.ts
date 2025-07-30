import { validateRequiredFields } from './validation';

describe('validateRequiredFields', () => {
  it('should return null when all fields are present', () => {
    const fields = [
      { value: 'test', fieldName: 'field1' },
      { value: 123, fieldName: 'field2' },
      { value: true, fieldName: 'field3' },
    ];

    const result = validateRequiredFields(fields);
    expect(result).toBeNull();
  });

  it('should return error when fields are missing', () => {
    const fields = [
      { value: '', fieldName: 'field1' },
      { value: null, fieldName: 'field2' },
      { value: undefined, fieldName: 'field3' },
      { value: 'valid', fieldName: 'field4' },
    ];

    const result = validateRequiredFields(fields);
    expect(result).toEqual(['field1', 'field2', 'field3']);
  });

  it('should handle empty array', () => {
    const result = validateRequiredFields([]);
    expect(result).toBeNull();
  });

  it('should handle falsy values correctly', () => {
    const fields = [
      { value: 0, fieldName: 'zero' },
      { value: false, fieldName: 'false' },
      { value: '', fieldName: 'empty' },
      { value: null, fieldName: 'null' },
    ];

    const result = validateRequiredFields(fields);
    expect(result).toEqual(['zero', 'false', 'empty', 'null']);
  });
});
