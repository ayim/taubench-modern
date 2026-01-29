import { describe, it, expect } from 'vitest';
import {
  JSONSchema,
  escapePointerToken,
  unescapePointerToken,
  pointerToPath,
  pathToPointer,
  jsonPointerToDotNotation,
  dotNotationToJsonPointer,
  parseFieldId,
  walk,
  buildIndex,
  findNodes,
  getChildren,
  getParent,
  addProperty,
  renameProperty,
  moveProperty,
  cloneProperty,
  getProperty,
  hasProperty,
  setProperty,
  updateProperty,
  deleteProperty,
  validateSchema,
  toRenderedDocumentSchema,
  computeSchema,
  RenderedField,
  toJSONDocumentSchema,
} from './schema-lib';

const getSchemaType = (schema: JSONSchema): string | undefined => {
  return (schema as { type?: string }).type;
};

const testSchema: JSONSchema = {
  type: 'object',
  properties: {
    name: {
      type: 'string',
      description: 'Full name',
    },
    email: {
      type: 'string',
      format: 'email',
    },
    age: {
      type: 'number',
      minimum: 0,
    },
    address: {
      type: 'object',
      properties: {
        city: {
          type: 'string',
        },
        street: {
          type: 'string',
        },
        zipCode: {
          type: 'string',
        },
      },
    },
    tags: {
      type: 'array',
      items: {
        type: 'string',
      },
    },
  },
};

describe('Pointer Utilities', () => {
  it('escapePointerToken handles ~ character', () => {
    const token = 'prop~name';
    const escaped = escapePointerToken(token);
    expect(escaped).toBe('prop~0name');
    expect(unescapePointerToken(escaped)).toBe(token);
  });

  it('escapePointerToken handles / character', () => {
    const token = 'prop/name';
    const escaped = escapePointerToken(token);
    expect(escaped).toBe('prop~1name');
    expect(unescapePointerToken(escaped)).toBe(token);
  });

  it('escapePointerToken roundtrip preserves special characters', () => {
    const token = '~0~1/~';
    const escaped = escapePointerToken(token);
    expect(unescapePointerToken(escaped)).toBe(token);
  });

  it('pointerToPath converts pointer to array', () => {
    const pointer = '/properties/user/properties/name';
    const path = pointerToPath(pointer);
    expect(path).toEqual(['properties', 'user', 'properties', 'name']);
  });

  it('pointerToPath handles root pointer', () => {
    const pointer = '';
    const path = pointerToPath(pointer);
    expect(path).toEqual([]);
  });

  it('pointerToPath handles escaped characters', () => {
    const pointer = '/properties/prop~0name/properties/sub~1prop';
    const path = pointerToPath(pointer);
    expect(path).toEqual(['properties', 'prop~name', 'properties', 'sub/prop']);
  });

  it('pathToPointer converts array to pointer', () => {
    const path = ['properties', 'user', 'properties', 'name'];
    const pointer = pathToPointer(path);
    expect(pointer).toBe('/properties/user/properties/name');
  });

  it('pathToPointer handles empty array', () => {
    const path: string[] = [];
    const pointer = pathToPointer(path);
    expect(pointer).toBe('');
  });

  it('pathToPointer escapes special characters', () => {
    const path = ['properties', 'prop~name', 'properties', 'sub/prop'];
    const pointer = pathToPointer(path);
    expect(pointer).toBe('/properties/prop~0name/properties/sub~1prop');
  });

  it('pathToPointer roundtrip with pointerToPath', () => {
    const originalPath = ['properties', 'prop~name', 'properties', 'sub/prop'];
    const pointer = pathToPointer(originalPath);
    const roundtripPath = pointerToPath(pointer);
    expect(roundtripPath).toEqual(originalPath);
  });
});

describe('jsonPointerToDotNotation', () => {
  it('converts simple property path', () => {
    expect(jsonPointerToDotNotation('/properties/name')).toBe('name');
  });

  it('converts nested property path', () => {
    expect(jsonPointerToDotNotation('/properties/address/properties/city')).toBe('address.city');
  });

  it('converts deeply nested property path', () => {
    expect(jsonPointerToDotNotation('/properties/address/properties/city/properties/zip')).toBe('address.city.zip');
  });

  it('returns empty string for non-property paths', () => {
    expect(jsonPointerToDotNotation('/items')).toBe('');
    expect(jsonPointerToDotNotation('')).toBe('');
    expect(jsonPointerToDotNotation('/some/other/path')).toBe('');
  });

  it('handles escaped characters in property names', () => {
    const pointer = '/properties/prop~0name/properties/sub~1prop';
    const dotNotation = jsonPointerToDotNotation(pointer);
    expect(dotNotation).toBe('prop~name.sub/prop');
  });

  it('handles empty root pointer', () => {
    expect(jsonPointerToDotNotation('')).toBe('');
  });
});

describe('dotNotationToJsonPointer', () => {
  it('converts simple field path', () => {
    expect(dotNotationToJsonPointer('name')).toBe('/properties/name');
  });

  it('converts nested field path', () => {
    expect(dotNotationToJsonPointer('address.city')).toBe('/properties/address/properties/city');
  });

  it('converts deeply nested field path', () => {
    expect(dotNotationToJsonPointer('address.city.zip')).toBe('/properties/address/properties/city/properties/zip');
  });

  it('returns empty string for empty input', () => {
    expect(dotNotationToJsonPointer('')).toBe('');
  });

  it('handles special characters in field names', () => {
    const dotNotation = 'prop~name.sub/prop';
    const pointer = dotNotationToJsonPointer(dotNotation);
    // Should escape special characters properly
    expect(pointer).toContain('properties');
    expect(pointer).toContain('prop~0name');
    expect(pointer).toContain('sub~1prop');
  });
});

describe('dotNotationToJsonPointer roundtrip with jsonPointerToDotNotation', () => {
  it('roundtrip for simple path', () => {
    const input = 'name';
    const asJsonPointer = dotNotationToJsonPointer(input);
    const backToDotNotation = jsonPointerToDotNotation(asJsonPointer);
    expect(backToDotNotation).toBe(input);
  });

  it('roundtrip for nested path', () => {
    const input = 'address.city';
    const asJsonPointer = dotNotationToJsonPointer(input);
    const backToDotNotation = jsonPointerToDotNotation(asJsonPointer);
    expect(backToDotNotation).toBe(input);
  });

  it('roundtrip for deeply nested path', () => {
    const input = 'address.city.zip';
    const asJsonPointer = dotNotationToJsonPointer(input);
    const backToDotNotation = jsonPointerToDotNotation(asJsonPointer);
    expect(backToDotNotation).toBe(input);
  });
});

describe('parseFieldId', () => {
  it('parses simple field to root parent', () => {
    const result = parseFieldId('name');
    expect(result).toEqual({
      parentPointer: '',
      propertyName: 'name',
    });
  });

  it('parses nested field to parent pointer', () => {
    const result = parseFieldId('address.city');
    expect(result).toEqual({
      parentPointer: '/properties/address',
      propertyName: 'city',
    });
  });

  it('parses deeply nested field', () => {
    const result = parseFieldId('user.address.city');
    expect(result).toEqual({
      parentPointer: '/properties/user/properties/address',
      propertyName: 'city',
    });
  });

  it('parses very deeply nested field', () => {
    const result = parseFieldId('user.profile.address.location.city');
    expect(result).toEqual({
      parentPointer: '/properties/user/properties/profile/properties/address/properties/location',
      propertyName: 'city',
    });
  });

  it('returns null for empty string', () => {
    const result = parseFieldId('');
    expect(result).toBeNull();
  });

  it('handles field names with special characters', () => {
    const result = parseFieldId('field~name.sub/prop');
    expect(result).not.toBeNull();
    expect(result?.propertyName).toBe('sub/prop');
    // Special characters get escaped in JSON Pointers: ~ becomes ~0, / becomes ~1
    expect(result?.parentPointer).toBe('/properties/field~0name');
  });

  it('extracts correct property name from single-level path', () => {
    const result = parseFieldId('email');
    expect(result?.propertyName).toBe('email');
    expect(result?.parentPointer).toBe('');
  });

  it('extracts correct property name from two-level path', () => {
    const result = parseFieldId('user.email');
    expect(result?.propertyName).toBe('email');
    expect(result?.parentPointer).toBe('/properties/user');
  });

  it('extracts correct property name from three-level path', () => {
    const result = parseFieldId('company.user.email');
    expect(result?.propertyName).toBe('email');
    expect(result?.parentPointer).toBe('/properties/company/properties/user');
  });
});

describe('Path Handling', () => {
  it('getProperty works with JSON Pointer paths', () => {
    const prop = getProperty(testSchema, '', 'name');
    expect(prop).toBeDefined();
  });

  it('walk returns JSON Pointer paths', () => {
    const visitedPointers: string[] = [];
    walk(testSchema, (node) => {
      visitedPointers.push(node.pointer);
    });

    expect(visitedPointers).toContain('/properties/name');
    expect(visitedPointers).toContain('/properties/address');
    expect(visitedPointers).toContain('/properties/tags');
    expect(visitedPointers).toContain('/properties/tags/items');
  });
});

describe('Schema Validation', () => {
  it('validateSchema passes for well-formed schema', () => {
    expect(() => validateSchema(testSchema)).not.toThrow();
  });

  it('validateSchema passes for schema with empty properties', () => {
    const schema: JSONSchema = {
      type: 'object',
      properties: {},
    };
    expect(() => validateSchema(schema)).not.toThrow();
  });

  it('validateSchema passes for schema with empty items', () => {
    const schema: JSONSchema = {
      type: 'array',
      items: {},
    };
    expect(() => validateSchema(schema)).not.toThrow();
  });

  it('validateSchema throws for object without properties', () => {
    const schema: JSONSchema = {
      type: 'object',
      // Missing properties
    };
    expect(() => validateSchema(schema)).toThrow(/missing 'properties' attribute/);
  });

  it('validateSchema throws for array without items', () => {
    const schema: JSONSchema = {
      type: 'array',
      // Missing items
    };
    expect(() => validateSchema(schema)).toThrow(/missing 'items' attribute/);
  });

  it('validateSchema throws for nested object without properties', () => {
    const schema: JSONSchema = {
      type: 'object',
      properties: {
        address: {
          type: 'object',
          // Missing properties
        },
      },
    };
    expect(() => validateSchema(schema)).toThrow(/missing 'properties' attribute/);
    expect(() => validateSchema(schema)).toThrow(/\/address/);
  });

  it('validateSchema throws for nested array without items', () => {
    const schema: JSONSchema = {
      type: 'object',
      properties: {
        tags: {
          type: 'array',
          // Missing items
        },
      },
    };
    expect(() => validateSchema(schema)).toThrow(/missing 'items' attribute/);
    expect(() => validateSchema(schema)).toThrow(/\/tags/);
  });

  it('validateSchema passes for implicit object (has properties but no type)', () => {
    const schema: JSONSchema = {
      properties: {
        name: { type: 'string' },
      },
    };
    // Implicit objects (no type but has properties) are valid
    expect(() => validateSchema(schema)).not.toThrow();
  });

  it('validateSchema passes for implicit array (has items but no type)', () => {
    const schema: JSONSchema = {
      items: { type: 'string' },
    };
    // Implicit arrays (no type but has items) are valid
    expect(() => validateSchema(schema)).not.toThrow();
  });

  it('validateSchema validates complex nested schema', () => {
    const complexSchema: JSONSchema = {
      type: 'object',
      properties: {
        users: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              tags: {
                type: 'array',
                items: { type: 'string' },
              },
            },
          },
        },
      },
    };
    expect(() => validateSchema(complexSchema)).not.toThrow();
  });

  it('validateSchema throws for complex nested schema with missing items', () => {
    const complexSchema: JSONSchema = {
      type: 'object',
      properties: {
        users: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              tags: {
                type: 'array',
                // Missing items
              },
            },
          },
        },
      },
    };
    expect(() => validateSchema(complexSchema)).toThrow(/missing 'items' attribute/);
    expect(() => validateSchema(complexSchema)).toThrow(/\/properties\/users\/items\/properties\/tags/);
  });
});

describe('Traversal', () => {
  it('walk visits all nodes in depth-first order', () => {
    const visitedPointers: string[] = [];
    walk(testSchema, (node) => {
      visitedPointers.push(node.pointer);
    });

    expect(visitedPointers.length).toBeGreaterThan(0);
    expect(visitedPointers[0]).toBe('');
  });

  it('walk visits expected schema nodes', () => {
    const visitedPointers: string[] = [];
    walk(testSchema, (node) => {
      visitedPointers.push(node.pointer);
    });

    expect(visitedPointers).toContain('/properties/name');
    expect(visitedPointers).toContain('/properties/address');
    expect(visitedPointers).toContain('/properties/address/properties/city');
    expect(visitedPointers).toContain('/properties/tags');
  });

  it('walk visits array items as separate nodes', () => {
    const visitedPointers: string[] = [];
    walk(testSchema, (node) => {
      visitedPointers.push(node.pointer);
    });

    expect(visitedPointers).toContain('/properties/tags/items');
  });

  it('walk provides correct node metadata', () => {
    let nameNodeFound = false;
    walk(testSchema, (node) => {
      if (node.pointer === '/properties/name') {
        expect(node.kind).toBe('scalar');
        expect(node.key).toBe('name');
        expect(node.parentPointer).toBe('');
        expect(getSchemaType(node.schema)).toBe('string');
        nameNodeFound = true;
      }
    });
    expect(nameNodeFound).toBe(true);
  });

  it('buildIndex creates index with all nodes', () => {
    const visitedPointers: string[] = [];
    walk(testSchema, (node) => {
      visitedPointers.push(node.pointer);
    });

    const index = buildIndex(testSchema);
    expect(index.size).toBe(visitedPointers.length);
  });

  it('buildIndex contains root node', () => {
    const index = buildIndex(testSchema);
    expect(index.has('')).toBe(true);
    expect(index.has('/properties/name')).toBe(true);
  });

  it('buildIndex indexed nodes have correct metadata', () => {
    const index = buildIndex(testSchema);
    const nameNode = index.get('/properties/name');

    expect(nameNode).toBeDefined();
    expect(nameNode?.kind).toBe('scalar');
    expect(nameNode?.key).toBe('name');
    expect(nameNode?.parentPointer).toBe('');
  });

  it('buildIndex correctly identifies node kinds', () => {
    const index = buildIndex(testSchema);

    const addressNode = index.get('/properties/address');
    expect(addressNode?.kind).toBe('object');

    const tagsNode = index.get('/properties/tags');
    expect(tagsNode?.kind).toBe('array');
  });
});

describe('Query Operations', () => {
  it('findNodes finds nodes matching predicate', () => {
    const stringNodes = findNodes(testSchema, (node) => getSchemaType(node.schema) === 'string');
    expect(stringNodes.length).toBeGreaterThan(0);
  });

  it('findNodes finds object nodes', () => {
    const objectNodes = findNodes(testSchema, (node) => node.kind === 'object');
    expect(objectNodes.length).toBeGreaterThan(0);
  });

  it('findNodes finds array nodes', () => {
    const arrayNodes = findNodes(testSchema, (node) => node.kind === 'array');
    expect(arrayNodes.length).toBeGreaterThan(0);
  });

  it('findNodes returns empty array when no matches', () => {
    const matches = findNodes(testSchema, () => false);
    expect(matches).toEqual([]);
  });

  it('getChildren returns children for object nodes', () => {
    const rootChildren = getChildren(testSchema, '');
    expect(rootChildren.length).toBeGreaterThan(0);
    expect(rootChildren.some((c) => c.key === 'name')).toBe(true);
  });

  it('getChildren returns children for nested objects', () => {
    const addressChildren = getChildren(testSchema, '/properties/address');
    expect(addressChildren.length).toBeGreaterThan(0);
    expect(addressChildren.some((c) => c.key === 'city')).toBe(true);
  });

  it('getChildren returns empty array for scalar nodes', () => {
    const nameChildren = getChildren(testSchema, '/properties/name');
    expect(nameChildren).toHaveLength(0);
  });

  it('getChildren returns children for array nodes', () => {
    const tagsChildren = getChildren(testSchema, '/properties/tags');
    expect(tagsChildren.length).toBeGreaterThan(0);
    expect(tagsChildren.some((c) => c.key === 'items')).toBe(true);
  });

  it('getChildren returns empty array for non-existent nodes', () => {
    const children = getChildren(testSchema, '/properties/nonexistent');
    expect(children).toEqual([]);
  });

  it('getParent returns parent for property nodes', () => {
    const nameParent = getParent(testSchema, '/properties/name');
    expect(nameParent).toBeDefined();
    expect(nameParent?.pointer).toBe('');
  });

  it('getParent returns parent for nested properties', () => {
    const cityParent = getParent(testSchema, '/properties/address/properties/city');
    expect(cityParent).toBeDefined();
    expect(cityParent?.pointer).toBe('/properties/address');
  });

  it('getParent returns undefined for root node', () => {
    const rootParent = getParent(testSchema, '');
    expect(rootParent).toBeUndefined();
  });

  it('getParent returns parent for nested properties', () => {
    const cityParent = getParent(testSchema, '/properties/address/properties/city');
    expect(cityParent).toBeDefined();
    expect(cityParent?.pointer).toBe('/properties/address');
  });

  it('getParent returns parent for array items', () => {
    const arrayObjectSchema: JSONSchema = {
      type: 'object',
      properties: {
        users: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
            },
          },
        },
      },
    };
    const usersParent = getParent(arrayObjectSchema, '/properties/users/items');
    expect(usersParent).toBeDefined();
    expect(usersParent?.pointer).toBe('/properties/users');
  });

  it('getParent return undefined for root node', () => {
    const rootParent = getParent(testSchema, '');
    expect(rootParent).toBeUndefined();
  });

  it('getParent returns parent even for non-existent nodes', () => {
    const parent = getParent(testSchema, '/properties/nonexistent');
    expect(parent).toBeDefined();
    expect(parent?.pointer).toBe('');
  });
});

describe('Property Operations', () => {
  it('getProperty gets root level property', () => {
    const nameSchema = getProperty(testSchema, '', 'name');
    expect(nameSchema).toBeDefined();
    expect(getSchemaType(nameSchema!)).toBe('string');
  });

  it('getProperty gets nested property', () => {
    const citySchema = getProperty(testSchema, '/properties/address', 'city');
    expect(citySchema).toBeDefined();
    expect(getSchemaType(citySchema!)).toBe('string');
  });

  it('getProperty returns undefined for non-existent property', () => {
    const nonExistent = getProperty(testSchema, '', 'doesNotExist');
    expect(nonExistent).toBeUndefined();
  });

  it('getProperty returns undefined for property on non-existent parent', () => {
    // Accessing property on non-existent parent - operation returns undefined
    // This is not a schema malformation issue, but an invalid navigation attempt
    const result = getProperty(testSchema, '/properties/doesNotExist', 'field');
    expect(result).toBeUndefined();
  });

  it('hasProperty returns true for existing root property', () => {
    expect(hasProperty(testSchema, '', 'name')).toBe(true);
  });

  it('hasProperty returns true for existing nested property', () => {
    expect(hasProperty(testSchema, '/properties/address', 'city')).toBe(true);
  });

  it('hasProperty returns false for non-existent property', () => {
    expect(hasProperty(testSchema, '', 'doesNotExist')).toBe(false);
  });

  it('hasProperty returns false for property on non-existent parent', () => {
    // Accessing property on non-existent parent - operation returns false
    // This is not a schema malformation issue, but an invalid navigation attempt
    expect(hasProperty(testSchema, '/properties/doesNotExist', 'field')).toBe(false);
  });

  it('setProperty sets new property schema', () => {
    const modified = setProperty(testSchema, '', 'name', {
      type: 'string',
      minLength: 1,
      maxLength: 100,
    });
    const updatedName = getProperty(modified, '', 'name') as { minLength?: number; maxLength?: number };
    expect(updatedName.minLength).toBe(1);
    expect(updatedName.maxLength).toBe(100);
  });

  it('setProperty replaces existing property schema', () => {
    const original = getProperty(testSchema, '', 'name') as { type?: string };
    const modified = setProperty(testSchema, '', 'name', { type: 'number' });
    const updated = getProperty(modified, '', 'name') as { type?: string };

    expect(original.type).toBe('string');
    expect(updated.type).toBe('number');
  });

  it('setProperty preserves original schema (immutable)', () => {
    const originalName = getProperty(testSchema, '', 'name');
    setProperty(testSchema, '', 'name', { type: 'number' });
    const afterName = getProperty(testSchema, '', 'name');

    expect(afterName).toEqual(originalName);
  });

  it('updateProperty updates property with new fields', () => {
    const modified = updateProperty(testSchema, '', 'name', (current) => ({
      ...(current as Record<string, unknown>),
      description: 'Full legal name',
    }));
    const nameNode = getProperty(modified, '', 'name') as { description?: string };
    expect(nameNode.description).toBe('Full legal name');
  });

  it('updateProperty preserves existing fields', () => {
    const modified = updateProperty(testSchema, '', 'name', (current) => ({
      ...(current as Record<string, unknown>),
      description: 'Full legal name',
    }));
    const nameNode = getProperty(modified, '', 'name') as { type?: string };
    expect(nameNode.type).toBe('string');
  });

  it('updateProperty preserves original schema (immutable)', () => {
    updateProperty(testSchema, '', 'name', (current) => ({
      ...(current as Record<string, unknown>),
      description: 'Full legal name',
    }));
    const origNameNode = getProperty(testSchema, '', 'name') as { description?: string };
    expect(origNameNode.description).not.toBe('Full legal name');
  });

  it('updateProperty adds constraint to existing property', () => {
    const modified = updateProperty(testSchema, '', 'age', (current) => ({
      ...(current as Record<string, unknown>),
      maximum: 120,
    }));
    const ageNode = getProperty(modified, '', 'age') as { maximum?: number; minimum?: number };
    expect(ageNode.maximum).toBe(120);
    expect(ageNode.minimum).toBe(0);
  });

  it('updateProperty adds custom attributes to scalar node', () => {
    const modified = updateProperty(testSchema, '', 'name', (current) => ({
      ...(current as Record<string, unknown>),
      'x-custom-field': 'custom value',
      'x-validation-rule': 'email-format',
    }));

    const nameNode = getProperty(modified, '', 'name') as Record<string, unknown>;
    expect(nameNode['x-custom-field']).toBe('custom value');
    expect(nameNode['x-validation-rule']).toBe('email-format');
    expect(nameNode.type).toBe('string');
  });

  it('deleteProperty removes specified property', () => {
    const modified = deleteProperty(testSchema, '', 'email');
    expect(hasProperty(modified, '', 'email')).toBe(false);
  });

  it('deleteProperty preserves original schema (immutable)', () => {
    deleteProperty(testSchema, '', 'email');
    expect(hasProperty(testSchema, '', 'email')).toBe(true);
  });

  it('deleteProperty preserves other properties', () => {
    const modified = deleteProperty(testSchema, '', 'email');
    expect(hasProperty(modified, '', 'name')).toBe(true);
    expect(hasProperty(modified, '', 'age')).toBe(true);
  });

  it('deleteProperty works with nested properties', () => {
    const modified = deleteProperty(testSchema, '/properties/address', 'city');
    expect(hasProperty(modified, '/properties/address', 'city')).toBe(false);
    expect(hasProperty(modified, '/properties/address', 'street')).toBe(true);
  });
});

describe('Specialized Mutations', () => {
  it('addProperty adds new property to root', () => {
    const modified = addProperty(testSchema, '', 'newField', {
      type: 'string',
      description: 'A new field',
    });
    expect(hasProperty(modified, '', 'newField')).toBe(true);
  });

  it('addProperty new property has correct schema', () => {
    const modified = addProperty(testSchema, '', 'newField', {
      type: 'string',
      description: 'A new field',
    });
    const newFieldNode = getProperty(modified, '', 'newField') as { type?: string; description?: string };
    expect(newFieldNode.type).toBe('string');
    expect(newFieldNode.description).toBe('A new field');
  });

  it('addProperty preserves original schema (immutable)', () => {
    addProperty(testSchema, '', 'newField', {
      type: 'string',
      description: 'A new field',
    });
    expect(hasProperty(testSchema, '', 'newField')).toBe(false);
  });

  it('addProperty adds property to nested object', () => {
    const modified = addProperty(testSchema, '/properties/address', 'state', {
      type: 'string',
    });
    expect(hasProperty(modified, '/properties/address', 'state')).toBe(true);
  });

  it('addProperty creates properties object if missing', () => {
    const schema: JSONSchema = { type: 'object' };
    const modified = addProperty(schema, '', 'field', { type: 'string' });
    expect(hasProperty(modified, '', 'field')).toBe(true);
  });

  it('renameProperty removes old property name', () => {
    const modified = renameProperty(testSchema, '', 'email', 'emailAddress');
    expect(hasProperty(modified, '', 'email')).toBe(false);
  });

  it('renameProperty adds new property name', () => {
    const modified = renameProperty(testSchema, '', 'email', 'emailAddress');
    expect(hasProperty(modified, '', 'emailAddress')).toBe(true);
  });

  it('renameProperty preserves property schema', () => {
    const modified = renameProperty(testSchema, '', 'email', 'emailAddress');
    const emailNode = getProperty(modified, '', 'emailAddress') as { format?: string };
    expect(emailNode.format).toBe('email');
  });

  it('renameProperty works with nested properties', () => {
    const modified = renameProperty(testSchema, '/properties/address', 'zipCode', 'postalCode');
    expect(hasProperty(modified, '/properties/address', 'zipCode')).toBe(false);
    expect(hasProperty(modified, '/properties/address', 'postalCode')).toBe(true);
  });

  it('renameProperty returns same schema if old and new names are identical', () => {
    const modified = renameProperty(testSchema, '', 'email', 'email');
    expect(modified).toBe(testSchema);
  });

  it('cloneProperty preserves original property', () => {
    const modified = cloneProperty(testSchema, '', 'name', '', 'fullName');
    expect(hasProperty(modified, '', 'name')).toBe(true);
  });

  it('cloneProperty creates cloned property', () => {
    const modified = cloneProperty(testSchema, '', 'name', '', 'fullName');
    expect(hasProperty(modified, '', 'fullName')).toBe(true);
  });

  it('cloneProperty clone has same schema as original', () => {
    const modified = cloneProperty(testSchema, '', 'name', '', 'fullName');
    const fullNameNode = getProperty(modified, '', 'fullName') as { type?: string; description?: string };
    const nameNode = getProperty(modified, '', 'name') as { type?: string; description?: string };
    expect(fullNameNode.type).toBe(nameNode.type);
    expect(fullNameNode.description).toBe(nameNode.description);
  });

  it('cloneProperty works across different parent objects', () => {
    const modified = cloneProperty(testSchema, '', 'email', '/properties/address', 'contactEmail');
    expect(hasProperty(modified, '', 'email')).toBe(true);
    expect(hasProperty(modified, '/properties/address', 'contactEmail')).toBe(true);
  });

  it('moveProperty removes property from original location', () => {
    const modified = moveProperty(testSchema, '', 'email', '/properties/address', 'email');
    expect(hasProperty(modified, '', 'email')).toBe(false);
  });

  it('moveProperty adds property to new location', () => {
    const modified = moveProperty(testSchema, '', 'email', '/properties/address', 'email');
    expect(hasProperty(modified, '/properties/address', 'email')).toBe(true);
  });

  it('moveProperty preserves property schema', () => {
    const modified = moveProperty(testSchema, '', 'email', '/properties/address', 'email');
    const movedEmailNode = getProperty(modified, '/properties/address', 'email') as { format?: string };
    expect(movedEmailNode.format).toBe('email');
  });

  it('moveProperty allows renaming during move', () => {
    const modified = moveProperty(testSchema, '', 'email', '/properties/address', 'contactEmail');
    expect(hasProperty(modified, '', 'email')).toBe(false);
    expect(hasProperty(modified, '/properties/address', 'contactEmail')).toBe(true);
  });
});

describe('Integration & Edge Cases', () => {
  it('builds nested object structure', () => {
    let schema = testSchema;
    schema = addProperty(schema, '', 'settings', {
      type: 'object',
      properties: {},
    });
    schema = addProperty(schema, '/properties/settings', 'locale', {
      type: 'string',
      default: 'en-US',
    });
    schema = addProperty(schema, '/properties/settings', 'timezone', {
      type: 'string',
      default: 'UTC',
    });

    expect(hasProperty(schema, '', 'settings')).toBe(true);
    expect(hasProperty(schema, '/properties/settings', 'locale')).toBe(true);
    expect(hasProperty(schema, '/properties/settings', 'timezone')).toBe(true);
  });

  it('reorganizes schema structure', () => {
    let schema = testSchema;
    schema = addProperty(schema, '', 'settings', {
      type: 'object',
      properties: {},
    });
    schema = addProperty(schema, '/properties/settings', 'locale', {
      type: 'string',
      default: 'en-US',
    });
    schema = addProperty(schema, '/properties/settings', 'timezone', {
      type: 'string',
      default: 'UTC',
    });

    schema = renameProperty(schema, '/properties/settings', 'locale', 'language');
    schema = moveProperty(schema, '/properties/settings', 'timezone', '', 'timezone');

    expect(hasProperty(schema, '/properties/settings', 'locale')).toBe(false);
    expect(hasProperty(schema, '/properties/settings', 'language')).toBe(true);
    expect(hasProperty(schema, '/properties/settings', 'timezone')).toBe(false);
    expect(hasProperty(schema, '', 'timezone')).toBe(true);
  });

  it('performs complex query and mutation workflow', () => {
    let schema = testSchema;
    schema = addProperty(schema, '', 'settings', {
      type: 'object',
      properties: {},
    });

    const allObjects = findNodes(schema, (node) => node.kind === 'object');
    expect(allObjects.length).toBeGreaterThan(0);

    const allStringProps = findNodes(schema, (node) => {
      const nodeType = getSchemaType(node.schema);
      return nodeType === 'string' && node.parentPointer !== null && node.key !== null && node.key !== 'items';
    });

    allStringProps.forEach((stringNode) => {
      if (stringNode.parentPointer !== null && stringNode.key !== null) {
        schema = updateProperty(schema, stringNode.parentPointer, stringNode.key, (current) => ({
          ...(current as Record<string, unknown>),
          'x-validated': true,
        }));
      }
    });

    const validatedCount = findNodes(
      schema,
      (node) => (node.schema as { 'x-validated'?: boolean })['x-validated'] === true,
    ).length;
    expect(validatedCount).toBeGreaterThan(0);
  });

  it('adds custom properties to all attributes in nested object', () => {
    let schema = testSchema;

    const addressChildren = getChildren(schema, '/properties/address');
    expect(addressChildren.length).toBeGreaterThan(0);

    addressChildren.forEach((child) => {
      if (child.key !== null) {
        schema = updateProperty(schema, '/properties/address', child.key, (current) => ({
          ...(current as Record<string, unknown>),
          'x-required-level': 'high',
          'x-pii': true,
          'x-category': 'address-component',
        }));
      }
    });

    const updatedChildren = getChildren(schema, '/properties/address');
    updatedChildren.forEach((child) => {
      if (child.key !== null) {
        const childSchema = getProperty(schema, '/properties/address', child.key) as Record<string, unknown>;
        expect(childSchema['x-required-level']).toBe('high');
        expect(childSchema['x-pii']).toBe(true);
        expect(childSchema['x-category']).toBe('address-component');
        expect(childSchema.type).toBeDefined();
      }
    });

    const nameSchema = getProperty(schema, '', 'name') as Record<string, unknown>;
    expect(nameSchema['x-pii']).toBeUndefined();
  });

  it('handles minimal scalar schema', () => {
    const minimalSchema: JSONSchema = {
      type: 'string',
    };

    const minimalIndex = buildIndex(minimalSchema);
    expect(minimalIndex.size).toBe(1);
    const rootNode = minimalIndex.get('');
    expect(rootNode).toBeDefined();
    expect(rootNode?.kind).toBe('scalar');
  });

  it('handles empty object schema', () => {
    const emptyObjectSchema: JSONSchema = {
      type: 'object',
      properties: {},
    };

    const emptyIndex = buildIndex(emptyObjectSchema);
    expect(emptyIndex.size).toBe(1);
    const rootNode = emptyIndex.get('');
    expect(rootNode).toBeDefined();
    expect(rootNode?.kind).toBe('object');

    const emptyChildren = getChildren(emptyObjectSchema, '');
    expect(emptyChildren).toHaveLength(0);
  });

  it('adds property to empty object schema', () => {
    const emptyObjectSchema: JSONSchema = {
      type: 'object',
      properties: {},
    };

    const withProperty = addProperty(emptyObjectSchema, '', 'newField', { type: 'string' });
    expect(hasProperty(withProperty, '', 'newField')).toBe(true);
  });

  it('handles deeply nested array schema', () => {
    const nestedArraySchema: JSONSchema = {
      type: 'array',
      items: {
        type: 'array',
        items: {
          type: 'array',
          items: {
            type: 'string',
          },
        },
      },
    };

    const nestedIndex = buildIndex(nestedArraySchema);
    expect(nestedIndex.size).toBeGreaterThan(1); // Should include root array and its items

    const level1Children = getChildren(nestedArraySchema, '');
    expect(level1Children.length).toBeGreaterThan(0); // Array root should have items as children
    expect(level1Children.some((c) => c.key === 'items')).toBe(true);
  });

  it('handles schema without type field', () => {
    const schemaWithoutType: JSONSchema = {
      properties: {
        field: { type: 'string' },
      },
    };

    const index = buildIndex(schemaWithoutType);
    expect(index.size).toBeGreaterThan(0);
    const rootNode = index.get('');
    expect(rootNode).toBeDefined();
    expect(rootNode?.kind).toBe('object');
  });

  it('handles schema with only items (implicit array)', () => {
    const implicitArray: JSONSchema = {
      items: { type: 'string' },
    };

    const index = buildIndex(implicitArray);
    const rootNode = index.get('');
    expect(rootNode).toBeDefined();
    expect(rootNode?.kind).toBe('array');
  });

  it('validateSchema catches array with no items schema', () => {
    const arrayWithoutItems: JSONSchema = {
      type: 'object',
      properties: {
        tags: {
          type: 'array',
          // No items property
        },
      },
    };

    // Validation should catch malformed schema upfront
    expect(() => validateSchema(arrayWithoutItems)).toThrow(/missing 'items' attribute/);
    expect(() => validateSchema(arrayWithoutItems)).toThrow(/\/properties\/tags/);
  });

  it('throws error when navigating into scalar values', () => {
    const schemaWithScalar: JSONSchema = {
      type: 'object',
      properties: {
        name: {
          type: 'string',
        },
      },
    };

    // Schema is well-formed
    validateSchema(schemaWithScalar);

    // When trying to navigate into a scalar, operations throw an error
    // This is not a schema malformation issue, but an invalid navigation attempt
    expect(() => hasProperty(schemaWithScalar, '/properties/name', 'subfield')).toThrow(
      /Invalid path: cannot navigate into scalar value at "\/properties\/name"/,
    );
    expect(() => getProperty(schemaWithScalar, '/properties/name', 'subfield')).toThrow(
      /Invalid path: cannot navigate into scalar value at "\/properties\/name"/,
    );
  });

  it('validateSchema catches object with no properties', () => {
    const objectWithoutProperties: JSONSchema = {
      type: 'object',
      // No properties field
    };

    // Validation should catch malformed schema upfront
    expect(() => validateSchema(objectWithoutProperties)).toThrow(/missing 'properties' attribute/);
  });

  it('handles non-existent properties in path resolution', () => {
    const schema: JSONSchema = {
      type: 'object',
      properties: {
        address: {
          type: 'object',
          properties: {
            city: { type: 'string' },
          },
        },
      },
    };

    // Property doesn't exist but path is valid - should return undefined/false
    // Note: '/properties/address' exists, 'state' doesn't - this is legitimate missing property
    const nonExistent = getProperty(schema, '/properties/address', 'state');
    expect(nonExistent).toBeUndefined();
    expect(hasProperty(schema, '/properties/address', 'state')).toBe(false);

    // Non-existent nested path - accessing property on non-existent parent
    // '/properties/address/properties/state' doesn't exist, so accessing 'code' on it returns undefined
    const deeplyNested = getProperty(schema, '/properties/address/properties/state', 'code');
    expect(deeplyNested).toBeUndefined();
  });

  it('handles array items path resolution correctly', () => {
    const arrayObjectSchema: JSONSchema = {
      type: 'object',
      properties: {
        users: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              contact: {
                type: 'object',
                properties: {
                  email: { type: 'string' },
                },
              },
            },
          },
        },
      },
    };

    // Should resolve path through array items
    const userNameSchema = getProperty(arrayObjectSchema, '/properties/users/items', 'name');
    expect(userNameSchema).toBeDefined();
    expect(getSchemaType(userNameSchema!)).toBe('string');

    // Should resolve nested path through array items
    const emailSchema = getProperty(arrayObjectSchema, '/properties/users/items/properties/contact', 'email');
    expect(emailSchema).toBeDefined();
    expect(getSchemaType(emailSchema!)).toBe('string');

    // Should handle hasProperty for array item properties
    expect(hasProperty(arrayObjectSchema, '/properties/users/items', 'name')).toBe(true);
    expect(hasProperty(arrayObjectSchema, '/properties/users/items/properties/contact', 'email')).toBe(true);

    // Should handle non-existent array item property
    expect(hasProperty(arrayObjectSchema, '/properties/users/items', 'age')).toBe(false);
  });

  it('handles complex nested array paths', () => {
    const complexNestedSchema: JSONSchema = {
      type: 'object',
      properties: {
        projects: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'string' },
              tasks: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    title: { type: 'string' },
                    metadata: {
                      type: 'object',
                      properties: {
                        priority: { type: 'number' },
                      },
                    },
                  },
                },
              },
            },
          },
        },
      },
    };

    // Should resolve deeply nested paths through arrays
    const taskTitleSchema = getProperty(
      complexNestedSchema,
      '/properties/projects/items/properties/tasks/items',
      'title',
    );
    expect(taskTitleSchema).toBeDefined();
    expect(getSchemaType(taskTitleSchema!)).toBe('string');

    // Should resolve nested object within array items
    const prioritySchema = getProperty(
      complexNestedSchema,
      '/properties/projects/items/properties/tasks/items/properties/metadata',
      'priority',
    );
    expect(prioritySchema).toBeDefined();
    expect(getSchemaType(prioritySchema!)).toBe('number');

    // Should handle hasProperty for nested array paths
    expect(hasProperty(complexNestedSchema, '/properties/projects/items/properties/tasks/items', 'title')).toBe(true);
    expect(
      hasProperty(
        complexNestedSchema,
        '/properties/projects/items/properties/tasks/items/properties/metadata',
        'priority',
      ),
    ).toBe(true);
  });

  it('handles path resolution when schema structure is incomplete', () => {
    const incompleteSchema: JSONSchema = {
      type: 'object',
      properties: {
        partial: {
          type: 'object',
          // Missing properties - just an empty object type
        },
      },
    };

    // Should handle gracefully when properties don't exist
    const children = getChildren(incompleteSchema, '/properties/partial');
    expect(children).toHaveLength(0);

    // When object has no properties field, validation should catch it upfront
    expect(() => validateSchema(incompleteSchema)).toThrow(/missing 'properties' attribute/);
  });
});

describe('toRenderedDocumentSchema', () => {
  it('parses simple schema with string properties', () => {
    const schema: JSONSchema = {
      description: 'Test schema',
      type: 'object',
      properties: {
        name: { type: 'string', description: 'The name' },
        age: { type: 'integer', description: 'The age' },
      },
    };

    const result = toRenderedDocumentSchema(schema);

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    expect(result.data).toEqual({
      description: 'Test schema',
      fields: [
        { id: 'name', name: 'name', type: 'text', description: 'The name', children: [] },
        { id: 'age', name: 'age', type: 'number', description: 'The age', children: [] },
      ],
    });
  });

  it('parses nested array schema', () => {
    const schema: JSONSchema = {
      type: 'object',
      properties: {
        tables: {
          type: 'array',
          description: 'Tables',
          items: {
            type: 'object',
            properties: {
              rows: {
                type: 'array',
                description: 'Rows',
                items: {
                  type: 'object',
                  properties: {
                    name: { type: 'string', description: 'Name field' },
                    email: { type: 'string', description: 'Email field' },
                  },
                },
              },
            },
          },
        },
      },
    };

    const result = toRenderedDocumentSchema(schema);

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    // Object arrays are wrapped in a synthetic __object_item__ container
    // for SchemaConfigurator compatibility
    expect(result.data).toEqual({
      description: undefined,
      fields: [
        {
          id: 'tables',
          name: 'tables',
          type: 'array',
          description: 'Tables',
          children: [
            {
              id: 'tables.__object_item__',
              name: '__object_item__',
              type: 'object',
              description: '',
              children: [
                {
                  id: 'tables.__object_item__.rows',
                  name: 'rows',
                  type: 'array',
                  description: 'Rows',
                  children: [
                    {
                      id: 'tables.__object_item__.rows.__object_item__',
                      name: '__object_item__',
                      type: 'object',
                      description: '',
                      children: [
                        {
                          id: 'tables.__object_item__.rows.__object_item__.name',
                          name: 'name',
                          type: 'text',
                          description: 'Name field',
                          children: [],
                        },
                        {
                          id: 'tables.__object_item__.rows.__object_item__.email',
                          name: 'email',
                          type: 'text',
                          description: 'Email field',
                          children: [],
                        },
                      ],
                    },
                  ],
                },
              ],
            },
          ],
        },
      ],
    });
  });

  it('returns empty fields for schema without properties', () => {
    const schema: JSONSchema = {
      type: 'object',
      description: 'Empty schema',
    };

    const result = toRenderedDocumentSchema(schema);

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    expect(result.data).toEqual({
      description: 'Empty schema',
      fields: [],
    });
  });

  it('handles schema with no description', () => {
    const schema: JSONSchema = {
      type: 'object',
      properties: {
        field: { type: 'string' },
      },
    };

    const result = toRenderedDocumentSchema(schema);

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    expect(result.data).toEqual({
      description: undefined,
      fields: [{ id: 'field', name: 'field', type: 'text', description: '', children: [] }],
    });
  });

  it('returns error for invalid schema', () => {
    const invalidSchema = { invalid: 'data' };

    const result = toRenderedDocumentSchema(invalidSchema);

    expect(result.success).toBe(false);
    if (result.success) throw new Error('Expected failure');

    expect(result.error).toEqual({
      code: 'invalid_schema',
      message: expect.stringContaining('The schema received from the server is invalid'),
    });
  });
});

describe('computeSchema', () => {
  const baseSchema: JSONSchema = {
    type: 'object',
    properties: {
      name: { type: 'string', description: 'The name' },
      email: { type: 'string', description: 'Email address' },
      address: {
        type: 'object',
        properties: {
          city: { type: 'string', description: 'City name' },
          zipCode: { type: 'string', description: 'Zip code' },
        },
      },
    },
  };

  it('returns unchanged schema when no options provided', () => {
    const result = computeSchema(baseSchema, {
      fieldsToAdd: [],
      fieldsToModify: [],
      fieldsToDelete: [],
    });

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    expect(result.data.schema).toEqual(baseSchema);
    expect(result.data.hasModifications).toBe(false);
    expect(result.data.modifications).toEqual([]);
  });

  it('deletes a root-level field', () => {
    const result = computeSchema(baseSchema, {
      fieldsToAdd: [],
      fieldsToModify: [],
      fieldsToDelete: ['email'],
    });

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    expect(hasProperty(result.data.schema, '', 'name')).toBe(true);
    expect(hasProperty(result.data.schema, '', 'email')).toBe(false);
    expect(hasProperty(result.data.schema, '', 'address')).toBe(true);

    expect(result.data.hasModifications).toBe(true);
    expect(result.data.modifications).toEqual([{ type: 'delete', fieldId: 'email' }]);
  });

  it('deletes a nested field', () => {
    const result = computeSchema(baseSchema, {
      fieldsToAdd: [],
      fieldsToModify: [],
      fieldsToDelete: ['address.zipCode'],
    });

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    expect(hasProperty(result.data.schema, '/properties/address', 'city')).toBe(true);
    expect(hasProperty(result.data.schema, '/properties/address', 'zipCode')).toBe(false);

    expect(result.data.hasModifications).toBe(true);
    expect(result.data.modifications).toEqual([{ type: 'delete', fieldId: 'address.zipCode' }]);
  });

  it('deletes multiple fields', () => {
    const result = computeSchema(baseSchema, {
      fieldsToAdd: [],
      fieldsToModify: [],
      fieldsToDelete: ['address', 'address.city'],
    });

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    expect(hasProperty(result.data.schema, '', 'address')).toBe(false);

    expect(result.data.hasModifications).toBe(true);
    expect(result.data.modifications).toEqual([
      { type: 'delete', fieldId: 'address.city' },
      { type: 'delete', fieldId: 'address' },
    ]);
  });

  it('modifies a field description', () => {
    const result = computeSchema(baseSchema, {
      fieldsToAdd: [],
      fieldsToModify: [{ fieldId: 'name', updates: { description: 'Updated name' } }],
      fieldsToDelete: [],
    });

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    const nameField = getProperty(result.data.schema, '', 'name') as { description?: string };
    expect(nameField.description).toBe('Updated name');

    expect(result.data.hasModifications).toBe(true);
    expect(result.data.modifications).toEqual([{ type: 'modify', fieldId: 'name' }]);
  });

  it('modifies a nested field', () => {
    const result = computeSchema(baseSchema, {
      fieldsToAdd: [],
      fieldsToModify: [{ fieldId: 'address.city', updates: { description: 'Updated city' } }],
      fieldsToDelete: [],
    });

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    const cityField = getProperty(result.data.schema, '/properties/address', 'city') as { description?: string };
    expect(cityField.description).toBe('Updated city');

    expect(result.data.hasModifications).toBe(true);
    expect(result.data.modifications).toEqual([{ type: 'modify', fieldId: 'address.city' }]);
  });

  it('preserves existing properties when modifying', () => {
    const result = computeSchema(baseSchema, {
      fieldsToAdd: [],
      fieldsToModify: [{ fieldId: 'name', updates: { description: 'New desc' } }],
      fieldsToDelete: [],
    });

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    const nameField = getProperty(result.data.schema, '', 'name') as { type?: string; description?: string };
    expect(nameField.type).toBe('string');
    expect(nameField.description).toBe('New desc');

    expect(result.data.hasModifications).toBe(true);
    expect(result.data.modifications).toEqual([{ type: 'modify', fieldId: 'name' }]);
  });

  it('adds a new root-level field', () => {
    const result = computeSchema(baseSchema, {
      fieldsToAdd: [{ fieldId: 'phone', schema: { type: 'string', description: 'Phone number' } }],
      fieldsToModify: [],
      fieldsToDelete: [],
    });

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    expect(hasProperty(result.data.schema, '', 'phone')).toBe(true);
    const phoneField = getProperty(result.data.schema, '', 'phone') as { type?: string; description?: string };
    expect(phoneField.type).toBe('string');
    expect(phoneField.description).toBe('Phone number');

    expect(result.data.hasModifications).toBe(true);
    expect(result.data.modifications).toEqual([{ type: 'add', fieldId: 'phone' }]);
  });

  it('adds a nested field', () => {
    const result = computeSchema(baseSchema, {
      fieldsToAdd: [{ fieldId: 'address.country', schema: { type: 'string' } }],
      fieldsToModify: [],
      fieldsToDelete: [],
    });

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    expect(hasProperty(result.data.schema, '/properties/address', 'country')).toBe(true);

    expect(result.data.hasModifications).toBe(true);
    expect(result.data.modifications).toEqual([{ type: 'add', fieldId: 'address.country' }]);
  });

  it('applies all operations in correct order', () => {
    const result = computeSchema(baseSchema, {
      fieldsToAdd: [{ fieldId: 'phone', schema: { type: 'string' } }],
      fieldsToDelete: ['email'],
      fieldsToModify: [{ fieldId: 'name', updates: { description: 'Modified' } }],
    });

    expect(result.success).toBe(true);
    if (!result.success) throw new Error('Expected success');

    // Delete worked
    expect(hasProperty(result.data.schema, '', 'email')).toBe(false);

    // Modify worked
    const nameField = getProperty(result.data.schema, '', 'name') as { description?: string };
    expect(nameField.description).toBe('Modified');

    // Add worked
    expect(hasProperty(result.data.schema, '', 'phone')).toBe(true);

    expect(result.data.hasModifications).toBe(true);
    expect(result.data.modifications).toEqual([
      { type: 'delete', fieldId: 'email' },
      { type: 'modify', fieldId: 'name' },
      { type: 'add', fieldId: 'phone' },
    ]);
  });

  it('is immutable - original schema unchanged', () => {
    computeSchema(baseSchema, {
      fieldsToAdd: [{ fieldId: 'phone', schema: { type: 'string' } }],
      fieldsToModify: [],
      fieldsToDelete: ['email'],
    });

    // Original should be unchanged
    expect(hasProperty(baseSchema, '', 'email')).toBe(true);
    expect(hasProperty(baseSchema, '', 'phone')).toBe(false);
  });
});

describe('toJSONDocumentSchema', () => {
  it('converts simple flat fields back to JSONSchema', () => {
    const fields: RenderedField[] = [
      { id: 'name', name: 'name', type: 'text', description: 'The name', children: [] },
      { id: 'age', name: 'age', type: 'number', description: 'The age', children: [] },
    ];

    const result = toJSONDocumentSchema(fields);

    expect(result).toEqual({
      type: 'object',
      properties: {
        name: { type: 'string', description: 'The name' },
        age: { type: 'number', description: 'The age' },
      },
    });
  });

  it('includes description when provided', () => {
    const fields: RenderedField[] = [{ id: 'name', name: 'name', type: 'text', description: '', children: [] }];

    const result = toJSONDocumentSchema(fields, 'Invoice schema');

    expect(result).toEqual({
      type: 'object',
      description: 'Invoice schema',
      properties: {
        name: { type: 'string' },
      },
    });
  });

  it('converts nested object fields', () => {
    const fields: RenderedField[] = [
      {
        id: 'address',
        name: 'address',
        type: 'object',
        description: 'User address',
        children: [
          { id: 'address.city', name: 'city', type: 'text', description: 'City', children: [] },
          { id: 'address.zip', name: 'zip', type: 'text', description: 'Zip code', children: [] },
        ],
      },
    ];

    const result = toJSONDocumentSchema(fields);

    expect(result).toEqual({
      type: 'object',
      properties: {
        address: {
          type: 'object',
          description: 'User address',
          properties: {
            city: { type: 'string', description: 'City' },
            zip: { type: 'string', description: 'Zip code' },
          },
        },
      },
    });
  });

  it('converts array fields with item properties', () => {
    const fields: RenderedField[] = [
      {
        id: 'items',
        name: 'items',
        type: 'array',
        description: 'Line items',
        children: [
          { id: 'items.sku', name: 'sku', type: 'text', description: '', children: [] },
          { id: 'items.price', name: 'price', type: 'number', description: '', children: [] },
        ],
      },
    ];

    const result = toJSONDocumentSchema(fields);

    expect(result).toEqual({
      type: 'object',
      properties: {
        items: {
          type: 'array',
          description: 'Line items',
          items: {
            type: 'object',
            properties: {
              sku: { type: 'string' },
              price: { type: 'number' },
            },
          },
        },
      },
    });
  });

  it('round-trips through toRenderedDocumentSchema and back', () => {
    const originalSchema: JSONSchema = {
      type: 'object',
      description: 'Invoice schema',
      properties: {
        invoice_id: { type: 'string', description: 'Invoice ID' },
        total: { type: 'number', description: 'Total amount' },
      },
    };

    const rendered = toRenderedDocumentSchema(originalSchema);
    expect(rendered.success).toBe(true);

    if (rendered.success) {
      const roundTripped = toJSONDocumentSchema(rendered.data.fields, rendered.data.description);
      expect(roundTripped).toEqual(originalSchema);
    }
  });

  it('returns empty properties for empty fields array', () => {
    const result = toJSONDocumentSchema([]);

    expect(result).toEqual({
      type: 'object',
      properties: {},
    });
  });

  it('converts primitive array (synthetic wrapper) back to simple items type', () => {
    // This tests that primitive arrays round-trip correctly through the ConfigurationSchema format
    const fields: RenderedField[] = [
      {
        id: 'tags',
        name: 'tags',
        type: 'array',
        description: 'Tags list',
        children: [
          // Synthetic wrapper created by parsePropertyToRenderedField for primitive arrays
          { id: 'tags.__primitive_item__', name: '__primitive_item__', type: 'text', description: '', children: [] },
        ],
      },
    ];

    const result = toJSONDocumentSchema(fields);

    expect(result).toEqual({
      type: 'object',
      properties: {
        tags: {
          type: 'array',
          description: 'Tags list',
          items: {
            type: 'string',
          },
        },
      },
    });
  });

  it('converts primitive array with description back correctly', () => {
    const fields: RenderedField[] = [
      {
        id: 'numbers',
        name: 'numbers',
        type: 'array',
        description: 'List of numbers',
        children: [
          {
            id: 'numbers.__primitive_item__',
            name: '__primitive_item__',
            type: 'number',
            description: 'A number value',
            children: [],
          },
        ],
      },
    ];

    const result = toJSONDocumentSchema(fields);

    expect(result).toEqual({
      type: 'object',
      properties: {
        numbers: {
          type: 'array',
          description: 'List of numbers',
          items: {
            type: 'number',
            description: 'A number value',
          },
        },
      },
    });
  });

  it('round-trips primitive array through toRenderedDocumentSchema and back', () => {
    const originalSchema: JSONSchema = {
      type: 'object',
      properties: {
        address_lines: {
          type: 'array',
          description: 'Address lines',
          items: {
            type: 'string',
            description: 'An address line',
          },
        },
      },
    };

    const rendered = toRenderedDocumentSchema(originalSchema);
    expect(rendered.success).toBe(true);

    if (rendered.success) {
      // Verify the synthetic wrapper was created
      expect(rendered.data.fields[0].children).toHaveLength(1);
      expect(rendered.data.fields[0].children[0].name).toBe('__primitive_item__');
      expect(rendered.data.fields[0].children[0].type).toBe('text');

      // Verify round-trip back to JSON Schema
      const roundTripped = toJSONDocumentSchema(rendered.data.fields);
      expect(roundTripped).toEqual(originalSchema);
    }
  });

  it('filters out synthetic wrapper when user adds fields to a primitive array', () => {
    // Simulates: user loads a primitive array, then adds a new field via SchemaConfigurator
    // The synthetic wrapper should be filtered out, keeping only the user-added fields
    const fieldsWithSyntheticAndUserAdded: RenderedField[] = [
      {
        id: 'line_items',
        name: 'line_items',
        type: 'array',
        description: 'Line items',
        children: [
          // Synthetic wrapper from original primitive array
          {
            id: 'line_items.__primitive_item__',
            name: '__primitive_item__',
            type: 'text',
            description: '',
            children: [],
          },
          // User-added field via SchemaConfigurator
          {
            id: 'line_items.product_name',
            name: 'product_name',
            type: 'text',
            description: 'Product name',
            children: [],
          },
          { id: 'line_items.amount', name: 'amount', type: 'number', description: 'Amount', children: [] },
        ],
      },
    ];

    const result = toJSONDocumentSchema(fieldsWithSyntheticAndUserAdded);

    // The synthetic __primitive_item__ should be filtered out
    expect(result).toEqual({
      type: 'object',
      properties: {
        line_items: {
          type: 'array',
          description: 'Line items',
          items: {
            type: 'object',
            properties: {
              product_name: { type: 'string', description: 'Product name' },
              amount: { type: 'number', description: 'Amount' },
            },
          },
        },
      },
    });
  });

  it('round-trips object array through toRenderedDocumentSchema and back', () => {
    const originalSchema: JSONSchema = {
      type: 'object',
      properties: {
        line_items: {
          type: 'array',
          description: 'Order line items',
          items: {
            type: 'object',
            properties: {
              product: { type: 'string', description: 'Product name' },
              quantity: { type: 'number', description: 'Quantity' },
              price: { type: 'number', description: 'Unit price' },
            },
          },
        },
      },
    };

    const rendered = toRenderedDocumentSchema(originalSchema);
    expect(rendered.success).toBe(true);

    if (rendered.success) {
      // Verify the synthetic container was created
      expect(rendered.data.fields[0].children).toHaveLength(1);
      expect(rendered.data.fields[0].children[0].name).toBe('__object_item__');
      expect(rendered.data.fields[0].children[0].type).toBe('object');
      expect(rendered.data.fields[0].children[0].children).toHaveLength(3);

      // Verify round-trip back to JSON Schema
      const roundTripped = toJSONDocumentSchema(rendered.data.fields);
      expect(roundTripped).toEqual(originalSchema);
    }
  });

  it('handles user adding fields to object array via SchemaConfigurator', () => {
    // Simulates: user loads an object array, then adds a new field
    // The synthetic __object_item__ container should be preserved and new field included
    const fieldsWithUserAddedField: RenderedField[] = [
      {
        id: 'line_items',
        name: 'line_items',
        type: 'array',
        description: 'Line items',
        children: [
          {
            id: 'line_items.__object_item__',
            name: '__object_item__',
            type: 'object',
            description: '',
            children: [
              {
                id: 'line_items.__object_item__.position',
                name: 'position',
                type: 'number',
                description: 'Row position',
                children: [],
              },
              // User-added field via SchemaConfigurator
              {
                id: 'line_items.__object_item__.product_name',
                name: 'product_name',
                type: 'text',
                description: 'Product name',
                children: [],
              },
            ],
          },
        ],
      },
    ];

    const result = toJSONDocumentSchema(fieldsWithUserAddedField);

    expect(result).toEqual({
      type: 'object',
      properties: {
        line_items: {
          type: 'array',
          description: 'Line items',
          items: {
            type: 'object',
            properties: {
              position: { type: 'number', description: 'Row position' },
              product_name: { type: 'string', description: 'Product name' },
            },
          },
        },
      },
    });
  });
});
