import { describe, it, expect } from 'vitest';
import {
  JSONSchema,
  escapePointerToken,
  unescapePointerToken,
  pointerToPath,
  pathToPointer,
  walk,
  buildIndex,
  findNodes,
  getChildren,
  getParent,
  addProperty,
  renameProperty,
  moveProperty,
  cloneProperty,
  propertyPointer,
  getProperty,
  hasProperty,
  setProperty,
  updateProperty,
  deleteProperty,
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

describe('Path Conversion', () => {
  it('propertyPointer returns logical paths for root', () => {
    const ptr = propertyPointer('', 'name');
    expect(ptr).toBe('/name');
  });

  it('propertyPointer returns logical paths for nested', () => {
    const ptr = propertyPointer('/address', 'city');
    expect(ptr).toBe('/address/city');
  });

  it('propertyPointer escapes special characters', () => {
    const ptr = propertyPointer('', 'prop/name');
    expect(ptr).toBe('/prop~1name');
  });

  it('getProperty works with logical paths', () => {
    const prop = getProperty(testSchema, '', 'name');
    expect(prop).toBeDefined();
  });

  it('walk returns logical paths not internal paths', () => {
    const visitedPointers: string[] = [];
    walk(testSchema, (node) => {
      visitedPointers.push(node.pointer);
    });

    expect(visitedPointers).toContain('/name');
    expect(visitedPointers).toContain('/address');
    expect(visitedPointers.some((p) => p.includes('/properties/'))).toBe(false);
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

    expect(visitedPointers).toContain('/name');
    expect(visitedPointers).toContain('/address');
    expect(visitedPointers).toContain('/address/city');
    expect(visitedPointers).toContain('/tags');
  });

  it('walk does not visit array items as separate nodes', () => {
    const visitedPointers: string[] = [];
    walk(testSchema, (node) => {
      visitedPointers.push(node.pointer);
    });

    expect(visitedPointers).not.toContain('/tags/items');
  });

  it('walk provides correct node metadata', () => {
    let nameNodeFound = false;
    walk(testSchema, (node) => {
      if (node.pointer === '/name') {
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
    expect(index.has('/name')).toBe(true);
  });

  it('buildIndex indexed nodes have correct metadata', () => {
    const index = buildIndex(testSchema);
    const nameNode = index.get('/name');

    expect(nameNode).toBeDefined();
    expect(nameNode?.kind).toBe('scalar');
    expect(nameNode?.key).toBe('name');
    expect(nameNode?.parentPointer).toBe('');
  });

  it('buildIndex correctly identifies node kinds', () => {
    const index = buildIndex(testSchema);

    const addressNode = index.get('/address');
    expect(addressNode?.kind).toBe('object');

    const tagsNode = index.get('/tags');
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
    const addressChildren = getChildren(testSchema, '/address');
    expect(addressChildren.length).toBeGreaterThan(0);
    expect(addressChildren.some((c) => c.key === 'city')).toBe(true);
  });

  it('getChildren returns empty array for scalar nodes', () => {
    const namePointer = propertyPointer('', 'name');
    const nameChildren = getChildren(testSchema, namePointer);
    expect(nameChildren).toHaveLength(0);
  });

  it('getChildren returns empty array for array nodes', () => {
    const tagsChildren = getChildren(testSchema, '/tags');
    expect(tagsChildren).toHaveLength(0);
  });

  it('getChildren returns empty array for non-existent nodes', () => {
    const children = getChildren(testSchema, '/nonexistent');
    expect(children).toEqual([]);
  });

  it('getParent returns parent for property nodes', () => {
    const nameParent = getParent(testSchema, propertyPointer('', 'name'));
    expect(nameParent).toBeDefined();
    expect(nameParent?.pointer).toBe('');
  });

  it('getParent returns parent for nested properties', () => {
    const cityParent = getParent(testSchema, propertyPointer('/address', 'city'));
    expect(cityParent).toBeDefined();
    expect(cityParent?.pointer).toBe('/address');
  });

  it('getParent returns undefined for root node', () => {
    const rootParent = getParent(testSchema, '');
    expect(rootParent).toBeUndefined();
  });

  it('getParent returns parent even for non-existent nodes', () => {
    const parent = getParent(testSchema, '/nonexistent');
    expect(parent).toBeDefined();
    expect(parent?.pointer).toBe('');
  });
});

describe('Property Operations', () => {
  it('propertyPointer builds logical path for root property', () => {
    const ptr = propertyPointer('', 'name');
    expect(ptr).toBe('/name');
  });

  it('propertyPointer builds logical path for nested property', () => {
    const ptr = propertyPointer('/address', 'city');
    expect(ptr).toBe('/address/city');
  });

  it('propertyPointer escapes special characters in property names', () => {
    const ptr = propertyPointer('', 'prop/name');
    expect(ptr).toBe('/prop~1name');
  });

  it('propertyPointer handles deeply nested paths', () => {
    const ptr = propertyPointer('/a/b/c', 'd');
    expect(ptr).toBe('/a/b/c/d');
  });

  it('getProperty gets root level property', () => {
    const nameSchema = getProperty(testSchema, '', 'name');
    expect(nameSchema).toBeDefined();
    expect(getSchemaType(nameSchema!)).toBe('string');
  });

  it('getProperty gets nested property', () => {
    const citySchema = getProperty(testSchema, '/address', 'city');
    expect(citySchema).toBeDefined();
    expect(getSchemaType(citySchema!)).toBe('string');
  });

  it('getProperty returns undefined for non-existent property', () => {
    const nonExistent = getProperty(testSchema, '', 'doesNotExist');
    expect(nonExistent).toBeUndefined();
  });

  it('getProperty returns undefined for property on non-existent parent', () => {
    const nonExistent = getProperty(testSchema, '/doesNotExist', 'field');
    expect(nonExistent).toBeUndefined();
  });

  it('hasProperty returns true for existing root property', () => {
    expect(hasProperty(testSchema, '', 'name')).toBe(true);
  });

  it('hasProperty returns true for existing nested property', () => {
    expect(hasProperty(testSchema, '/address', 'city')).toBe(true);
  });

  it('hasProperty returns false for non-existent property', () => {
    expect(hasProperty(testSchema, '', 'doesNotExist')).toBe(false);
  });

  it('hasProperty returns false for property on non-existent parent', () => {
    expect(hasProperty(testSchema, '/doesNotExist', 'field')).toBe(false);
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
    const modified = deleteProperty(testSchema, '/address', 'city');
    expect(hasProperty(modified, '/address', 'city')).toBe(false);
    expect(hasProperty(modified, '/address', 'street')).toBe(true);
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
    const modified = addProperty(testSchema, '/address', 'state', {
      type: 'string',
    });
    expect(hasProperty(modified, '/address', 'state')).toBe(true);
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
    const modified = renameProperty(testSchema, '/address', 'zipCode', 'postalCode');
    expect(hasProperty(modified, '/address', 'zipCode')).toBe(false);
    expect(hasProperty(modified, '/address', 'postalCode')).toBe(true);
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
    const modified = cloneProperty(testSchema, '', 'email', '/address', 'contactEmail');
    expect(hasProperty(modified, '', 'email')).toBe(true);
    expect(hasProperty(modified, '/address', 'contactEmail')).toBe(true);
  });

  it('moveProperty removes property from original location', () => {
    const modified = moveProperty(testSchema, '', 'email', '/address', 'email');
    expect(hasProperty(modified, '', 'email')).toBe(false);
  });

  it('moveProperty adds property to new location', () => {
    const modified = moveProperty(testSchema, '', 'email', '/address', 'email');
    expect(hasProperty(modified, '/address', 'email')).toBe(true);
  });

  it('moveProperty preserves property schema', () => {
    const modified = moveProperty(testSchema, '', 'email', '/address', 'email');
    const movedEmailNode = getProperty(modified, '/address', 'email') as { format?: string };
    expect(movedEmailNode.format).toBe('email');
  });

  it('moveProperty allows renaming during move', () => {
    const modified = moveProperty(testSchema, '', 'email', '/address', 'contactEmail');
    expect(hasProperty(modified, '', 'email')).toBe(false);
    expect(hasProperty(modified, '/address', 'contactEmail')).toBe(true);
  });
});

describe('Integration & Edge Cases', () => {
  it('builds nested object structure', () => {
    let schema = testSchema;
    schema = addProperty(schema, '', 'settings', {
      type: 'object',
      properties: {},
    });
    schema = addProperty(schema, '/settings', 'locale', {
      type: 'string',
      default: 'en-US',
    });
    schema = addProperty(schema, '/settings', 'timezone', {
      type: 'string',
      default: 'UTC',
    });

    expect(hasProperty(schema, '', 'settings')).toBe(true);
    expect(hasProperty(schema, '/settings', 'locale')).toBe(true);
    expect(hasProperty(schema, '/settings', 'timezone')).toBe(true);
  });

  it('reorganizes schema structure', () => {
    let schema = testSchema;
    schema = addProperty(schema, '', 'settings', {
      type: 'object',
      properties: {},
    });
    schema = addProperty(schema, '/settings', 'locale', {
      type: 'string',
      default: 'en-US',
    });
    schema = addProperty(schema, '/settings', 'timezone', {
      type: 'string',
      default: 'UTC',
    });

    schema = renameProperty(schema, '/settings', 'locale', 'language');
    schema = moveProperty(schema, '/settings', 'timezone', '', 'timezone');

    expect(hasProperty(schema, '/settings', 'locale')).toBe(false);
    expect(hasProperty(schema, '/settings', 'language')).toBe(true);
    expect(hasProperty(schema, '/settings', 'timezone')).toBe(false);
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

    const addressChildren = getChildren(schema, '/address');
    expect(addressChildren.length).toBeGreaterThan(0);

    addressChildren.forEach((child) => {
      if (child.key !== null) {
        schema = updateProperty(schema, '/address', child.key, (current) => ({
          ...(current as Record<string, unknown>),
          'x-required-level': 'high',
          'x-pii': true,
          'x-category': 'address-component',
        }));
      }
    });

    const updatedChildren = getChildren(schema, '/address');
    updatedChildren.forEach((child) => {
      if (child.key !== null) {
        const childSchema = getProperty(schema, '/address', child.key) as Record<string, unknown>;
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
    expect(nestedIndex.size).toBe(1);

    const level1Children = getChildren(nestedArraySchema, '');
    expect(level1Children).toHaveLength(0);
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
});
