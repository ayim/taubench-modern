/**
 * Unit tests for JSON Schema Library
 */

import {
  // Types
  JSONSchema,
  // Pointer utilities (Public)
  escapePointerToken,
  unescapePointerToken,
  pointerToPath,
  pathToPointer,
  // Traversal (Public)
  walk,
  buildIndex,
  // Query operations (Public)
  findNodes,
  getChildren,
  getParent,
  // Specialized mutations (Public)
  addProperty,
  renameProperty,
  moveProperty,
  cloneProperty,
  // Convenience functions (Public - Primary API)
  propertyPointer,
  getProperty,
  hasProperty,
  setProperty,
  updateProperty,
  deleteProperty,
} from './schema-lib';

// Simple test runner (same pattern as dataTransformations.test.ts)
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

/**
 * Deep equality check for objects and arrays
 * Recursively compares nested structures
 */
function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a == null || b == null) return false;
  if (typeof a !== typeof b) return false;
  if (typeof a !== 'object') return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;

  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    return a.every((val, idx) => deepEqual(val, b[idx]));
  }

  const keysA = Object.keys(a as Record<string, unknown>);
  const keysB = Object.keys(b as Record<string, unknown>);
  if (keysA.length !== keysB.length) return false;

  return keysA.every((key) => deepEqual((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key]));
}

/**
 * Helper to extract type from a JSON Schema node
 */
function getSchemaType(schema: JSONSchema): string | undefined {
  return (schema as { type?: string }).type;
}

/**
 * Test schema with various property types (string, number, object, array)
 * Used to verify traversal, query, and mutation operations across different schema structures
 */
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

/* ========================================================================
   LOW-LEVEL UTILITIES
   ======================================================================== */

// Pointer Utilities
runTest('escapePointerToken handles ~ character', () => {
  const token = 'prop~name';
  const escaped = escapePointerToken(token);
  if (escaped !== 'prop~0name') {
    throw new Error(`Expected "prop~0name", got "${escaped}"`);
  }
  if (unescapePointerToken(escaped) !== token) {
    throw new Error(`Roundtrip failed: expected "${token}", got "${unescapePointerToken(escaped)}"`);
  }
});

runTest('escapePointerToken handles / character', () => {
  const token = 'prop/name';
  const escaped = escapePointerToken(token);
  if (escaped !== 'prop~1name') {
    throw new Error(`Expected "prop~1name", got "${escaped}"`);
  }
  if (unescapePointerToken(escaped) !== token) {
    throw new Error(`Roundtrip failed: expected "${token}", got "${unescapePointerToken(escaped)}"`);
  }
});

runTest('escapePointerToken roundtrip preserves special characters', () => {
  const token = '~0~1/~';
  const escaped = escapePointerToken(token);
  if (unescapePointerToken(escaped) !== token) {
    throw new Error(`Roundtrip failed: expected "${token}", got "${unescapePointerToken(escaped)}"`);
  }
});

runTest('pointerToPath converts pointer to array', () => {
  const pointer = '/properties/user/properties/name';
  const path = pointerToPath(pointer);
  if (!deepEqual(path, ['properties', 'user', 'properties', 'name'])) {
    throw new Error(`Expected ["properties", "user", "properties", "name"], got ${JSON.stringify(path)}`);
  }
});

runTest('pointerToPath handles root pointer', () => {
  const pointer = '';
  const path = pointerToPath(pointer);
  if (!deepEqual(path, [])) {
    throw new Error(`Expected [], got ${JSON.stringify(path)}`);
  }
});

runTest('pointerToPath handles escaped characters', () => {
  const pointer = '/properties/prop~0name/properties/sub~1prop';
  const path = pointerToPath(pointer);
  if (!deepEqual(path, ['properties', 'prop~name', 'properties', 'sub/prop'])) {
    throw new Error(`Expected ["properties", "prop~name", "properties", "sub/prop"], got ${JSON.stringify(path)}`);
  }
});

runTest('pathToPointer converts array to pointer', () => {
  const path = ['properties', 'user', 'properties', 'name'];
  const pointer = pathToPointer(path);
  if (pointer !== '/properties/user/properties/name') {
    throw new Error(`Expected "/properties/user/properties/name", got "${pointer}"`);
  }
});

runTest('pathToPointer handles empty array', () => {
  const path: string[] = [];
  const pointer = pathToPointer(path);
  if (pointer !== '') {
    throw new Error(`Expected "", got "${pointer}"`);
  }
});

runTest('pathToPointer escapes special characters', () => {
  const path = ['properties', 'prop~name', 'properties', 'sub/prop'];
  const pointer = pathToPointer(path);
  if (pointer !== '/properties/prop~0name/properties/sub~1prop') {
    throw new Error(`Expected "/properties/prop~0name/properties/sub~1prop", got "${pointer}"`);
  }
});

runTest('pathToPointer roundtrip with pointerToPath', () => {
  const originalPath = ['properties', 'prop~name', 'properties', 'sub/prop'];
  const pointer = pathToPointer(originalPath);
  const roundtripPath = pointerToPath(pointer);
  if (!deepEqual(roundtripPath, originalPath)) {
    throw new Error(`Roundtrip failed: expected ${JSON.stringify(originalPath)}, got ${JSON.stringify(roundtripPath)}`);
  }
});

// Path Conversion
runTest('propertyPointer returns logical paths for root', () => {
  const ptr = propertyPointer('', 'name');
  if (ptr !== '/name') {
    throw new Error(`Expected "/name", got "${ptr}"`);
  }
});

runTest('propertyPointer returns logical paths for nested', () => {
  const ptr = propertyPointer('/address', 'city');
  if (ptr !== '/address/city') {
    throw new Error(`Expected "/address/city", got "${ptr}"`);
  }
});

runTest('propertyPointer escapes special characters', () => {
  const ptr = propertyPointer('', 'prop/name');
  if (ptr !== '/prop~1name') {
    throw new Error(`Expected "/prop~1name", got "${ptr}"`);
  }
});

runTest('getProperty works with logical paths', () => {
  const prop = getProperty(testSchema, '', 'name');
  if (!prop) {
    throw new Error('Expected property to be defined');
  }
});

runTest('walk returns logical paths not internal paths', () => {
  const visitedPointers: string[] = [];
  walk(testSchema, (node) => {
    visitedPointers.push(node.pointer);
  });

  if (!visitedPointers.includes('/name')) {
    throw new Error('Expected /name to be in visited pointers');
  }
  if (!visitedPointers.includes('/address')) {
    throw new Error('Expected /address to be in visited pointers');
  }
  if (visitedPointers.some((p) => p.includes('/properties/'))) {
    throw new Error('Expected no internal paths with /properties/');
  }
});

/* ========================================================================
   PUBLIC API - TRAVERSAL
   ======================================================================== */

runTest('walk visits all nodes in depth-first order', () => {
  const visitedPointers: string[] = [];
  walk(testSchema, (node) => {
    visitedPointers.push(node.pointer);
  });

  if (visitedPointers.length === 0) {
    throw new Error('Expected at least one visited node');
  }
  if (visitedPointers[0] !== '') {
    throw new Error(`Expected root node first, got "${visitedPointers[0]}"`);
  }
});

runTest('walk visits expected schema nodes', () => {
  const visitedPointers: string[] = [];
  walk(testSchema, (node) => {
    visitedPointers.push(node.pointer);
  });

  if (!visitedPointers.includes('/name')) {
    throw new Error('Expected /name to be visited');
  }
  if (!visitedPointers.includes('/address')) {
    throw new Error('Expected /address to be visited');
  }
  if (!visitedPointers.includes('/address/city')) {
    throw new Error('Expected /address/city to be visited');
  }
  if (!visitedPointers.includes('/tags')) {
    throw new Error('Expected /tags to be visited');
  }
});

runTest('walk does not visit array items as separate nodes', () => {
  const visitedPointers: string[] = [];
  walk(testSchema, (node) => {
    visitedPointers.push(node.pointer);
  });

  if (visitedPointers.includes('/tags/items')) {
    throw new Error('Expected /tags/items not to be visited as separate node');
  }
});

runTest('walk provides correct node metadata', () => {
  let nameNodeFound = false;
  walk(testSchema, (node) => {
    if (node.pointer === '/name') {
      if (node.kind !== 'scalar') {
        throw new Error(`Expected kind "scalar", got "${node.kind}"`);
      }
      if (node.key !== 'name') {
        throw new Error(`Expected key "name", got "${node.key}"`);
      }
      if (node.parentPointer !== '') {
        throw new Error(`Expected parentPointer "", got "${node.parentPointer}"`);
      }
      if (getSchemaType(node.schema) !== 'string') {
        throw new Error(`Expected schema.type "string", got "${getSchemaType(node.schema)}"`);
      }
      nameNodeFound = true;
    }
  });
  if (!nameNodeFound) {
    throw new Error('Expected name node to be found');
  }
});

runTest('buildIndex creates index with all nodes', () => {
  const visitedPointers: string[] = [];
  walk(testSchema, (node) => {
    visitedPointers.push(node.pointer);
  });

  const index = buildIndex(testSchema);
  if (index.size !== visitedPointers.length) {
    throw new Error(`Expected index size ${visitedPointers.length}, got ${index.size}`);
  }
});

runTest('buildIndex contains root node', () => {
  const index = buildIndex(testSchema);
  if (!index.has('')) {
    throw new Error('Expected index to contain root node');
  }
  if (!index.has('/name')) {
    throw new Error('Expected index to contain /name node');
  }
});

runTest('buildIndex indexed nodes have correct metadata', () => {
  const index = buildIndex(testSchema);
  const nameNode = index.get('/name');

  if (!nameNode) {
    throw new Error('Expected name node to be defined');
  }
  if (nameNode.kind !== 'scalar') {
    throw new Error(`Expected kind "scalar", got "${nameNode.kind}"`);
  }
  if (nameNode.key !== 'name') {
    throw new Error(`Expected key "name", got "${nameNode.key}"`);
  }
  if (nameNode.parentPointer !== '') {
    throw new Error(`Expected parentPointer "", got "${nameNode.parentPointer}"`);
  }
});

runTest('buildIndex correctly identifies node kinds', () => {
  const index = buildIndex(testSchema);

  const addressNode = index.get('/address');
  if (!addressNode) {
    throw new Error('Expected address node to be defined');
  }
  if (addressNode.kind !== 'object') {
    throw new Error(`Expected kind "object", got "${addressNode.kind}"`);
  }

  const tagsNode = index.get('/tags');
  if (!tagsNode) {
    throw new Error('Expected tags node to be defined');
  }
  if (tagsNode.kind !== 'array') {
    throw new Error(`Expected kind "array", got "${tagsNode.kind}"`);
  }
});

/* ========================================================================
   PUBLIC API - QUERY OPERATIONS
   ======================================================================== */

runTest('findNodes finds nodes matching predicate', () => {
  const stringNodes = findNodes(testSchema, (node) => getSchemaType(node.schema) === 'string');
  if (stringNodes.length === 0) {
    throw new Error('Expected to find at least one string node');
  }
});

runTest('findNodes finds object nodes', () => {
  const objectNodes = findNodes(testSchema, (node) => node.kind === 'object');
  if (objectNodes.length === 0) {
    throw new Error('Expected to find at least one object node');
  }
});

runTest('findNodes finds array nodes', () => {
  const arrayNodes = findNodes(testSchema, (node) => node.kind === 'array');
  if (arrayNodes.length === 0) {
    throw new Error('Expected to find at least one array node');
  }
});

runTest('findNodes returns empty array when no matches', () => {
  const matches = findNodes(testSchema, () => false);
  if (!deepEqual(matches, [])) {
    throw new Error(`Expected empty array, got ${JSON.stringify(matches)}`);
  }
});

runTest('getChildren returns children for object nodes', () => {
  const rootChildren = getChildren(testSchema, '');
  if (rootChildren.length === 0) {
    throw new Error('Expected at least one child');
  }
  if (!rootChildren.some((c) => c.key === 'name')) {
    throw new Error("Expected to find child with key 'name'");
  }
});

runTest('getChildren returns children for nested objects', () => {
  const addressChildren = getChildren(testSchema, '/address');
  if (addressChildren.length === 0) {
    throw new Error('Expected at least one child');
  }
  if (!addressChildren.some((c) => c.key === 'city')) {
    throw new Error("Expected to find child with key 'city'");
  }
});

runTest('getChildren returns empty array for scalar nodes', () => {
  const namePointer = propertyPointer('', 'name');
  const nameChildren = getChildren(testSchema, namePointer);
  if (nameChildren.length !== 0) {
    throw new Error(`Expected empty array, got ${nameChildren.length} children`);
  }
});

runTest('getChildren returns empty array for array nodes', () => {
  const tagsChildren = getChildren(testSchema, '/tags');
  if (tagsChildren.length !== 0) {
    throw new Error(`Expected empty array, got ${tagsChildren.length} children`);
  }
});

runTest('getChildren returns empty array for non-existent nodes', () => {
  const children = getChildren(testSchema, '/nonexistent');
  if (!deepEqual(children, [])) {
    throw new Error(`Expected empty array, got ${JSON.stringify(children)}`);
  }
});

runTest('getParent returns parent for property nodes', () => {
  const nameParent = getParent(testSchema, propertyPointer('', 'name'));
  if (!nameParent) {
    throw new Error('Expected parent to be defined');
  }
  if (nameParent.pointer !== '') {
    throw new Error(`Expected parent pointer "", got "${nameParent.pointer}"`);
  }
});

runTest('getParent returns parent for nested properties', () => {
  const cityParent = getParent(testSchema, propertyPointer('/address', 'city'));
  if (!cityParent) {
    throw new Error('Expected parent to be defined');
  }
  if (cityParent.pointer !== '/address') {
    throw new Error(`Expected parent pointer "/address", got "${cityParent.pointer}"`);
  }
});

runTest('getParent returns undefined for root node', () => {
  const rootParent = getParent(testSchema, '');
  if (rootParent !== undefined) {
    throw new Error(`Expected undefined, got ${JSON.stringify(rootParent)}`);
  }
});

runTest('getParent returns parent even for non-existent nodes', () => {
  const parent = getParent(testSchema, '/nonexistent');
  if (!parent) {
    throw new Error('Expected parent to be defined');
  }
  if (parent.pointer !== '') {
    throw new Error(`Expected parent pointer "", got "${parent.pointer}"`);
  }
});

/* ========================================================================
   PUBLIC API - PROPERTY OPERATIONS
   ======================================================================== */

runTest('propertyPointer builds logical path for root property', () => {
  const ptr = propertyPointer('', 'name');
  if (ptr !== '/name') {
    throw new Error(`Expected "/name", got "${ptr}"`);
  }
});

runTest('propertyPointer builds logical path for nested property', () => {
  const ptr = propertyPointer('/address', 'city');
  if (ptr !== '/address/city') {
    throw new Error(`Expected "/address/city", got "${ptr}"`);
  }
});

runTest('propertyPointer escapes special characters in property names', () => {
  const ptr = propertyPointer('', 'prop/name');
  if (ptr !== '/prop~1name') {
    throw new Error(`Expected "/prop~1name", got "${ptr}"`);
  }
});

runTest('propertyPointer handles deeply nested paths', () => {
  const ptr = propertyPointer('/a/b/c', 'd');
  if (ptr !== '/a/b/c/d') {
    throw new Error(`Expected "/a/b/c/d", got "${ptr}"`);
  }
});

runTest('getProperty gets root level property', () => {
  const nameSchema = getProperty(testSchema, '', 'name');
  if (!nameSchema) {
    throw new Error('Expected property to be defined');
  }
  if (getSchemaType(nameSchema) !== 'string') {
    throw new Error(`Expected type "string", got "${getSchemaType(nameSchema)}"`);
  }
});

runTest('getProperty gets nested property', () => {
  const citySchema = getProperty(testSchema, '/address', 'city');
  if (!citySchema) {
    throw new Error('Expected property to be defined');
  }
  if (getSchemaType(citySchema) !== 'string') {
    throw new Error(`Expected type "string", got "${getSchemaType(citySchema)}"`);
  }
});

runTest('getProperty returns undefined for non-existent property', () => {
  const nonExistent = getProperty(testSchema, '', 'doesNotExist');
  if (nonExistent !== undefined) {
    throw new Error(`Expected undefined, got ${JSON.stringify(nonExistent)}`);
  }
});

runTest('getProperty returns undefined for property on non-existent parent', () => {
  const nonExistent = getProperty(testSchema, '/doesNotExist', 'field');
  if (nonExistent !== undefined) {
    throw new Error(`Expected undefined, got ${JSON.stringify(nonExistent)}`);
  }
});

runTest('hasProperty returns true for existing root property', () => {
  if (!hasProperty(testSchema, '', 'name')) {
    throw new Error('Expected hasProperty to return true');
  }
});

runTest('hasProperty returns true for existing nested property', () => {
  if (!hasProperty(testSchema, '/address', 'city')) {
    throw new Error('Expected hasProperty to return true');
  }
});

runTest('hasProperty returns false for non-existent property', () => {
  if (hasProperty(testSchema, '', 'doesNotExist')) {
    throw new Error('Expected hasProperty to return false');
  }
});

runTest('hasProperty returns false for property on non-existent parent', () => {
  if (hasProperty(testSchema, '/doesNotExist', 'field')) {
    throw new Error('Expected hasProperty to return false');
  }
});

runTest('setProperty sets new property schema', () => {
  const modified = setProperty(testSchema, '', 'name', {
    type: 'string',
    minLength: 1,
    maxLength: 100,
  });
  const updatedName = getProperty(modified, '', 'name') as { minLength?: number; maxLength?: number };
  if (updatedName.minLength !== 1) {
    throw new Error(`Expected minLength 1, got ${updatedName.minLength}`);
  }
  if (updatedName.maxLength !== 100) {
    throw new Error(`Expected maxLength 100, got ${updatedName.maxLength}`);
  }
});

runTest('setProperty replaces existing property schema', () => {
  const original = getProperty(testSchema, '', 'name') as { type?: string };
  const modified = setProperty(testSchema, '', 'name', { type: 'number' });
  const updated = getProperty(modified, '', 'name') as { type?: string };

  if (original.type !== 'string') {
    throw new Error(`Expected original type "string", got "${original.type}"`);
  }
  if (updated.type !== 'number') {
    throw new Error(`Expected updated type "number", got "${updated.type}"`);
  }
});

runTest('setProperty preserves original schema (immutable)', () => {
  const originalName = getProperty(testSchema, '', 'name');
  setProperty(testSchema, '', 'name', { type: 'number' });
  const afterName = getProperty(testSchema, '', 'name');

  if (!deepEqual(originalName, afterName)) {
    throw new Error('Expected original schema to be unchanged');
  }
});

runTest('updateProperty updates property with new fields', () => {
  const modified = updateProperty(testSchema, '', 'name', (current) => ({
    ...(current as Record<string, unknown>),
    description: 'Full legal name',
  }));
  const nameNode = getProperty(modified, '', 'name') as { description?: string };
  if (nameNode.description !== 'Full legal name') {
    throw new Error(`Expected description "Full legal name", got "${nameNode.description}"`);
  }
});

runTest('updateProperty preserves existing fields', () => {
  const modified = updateProperty(testSchema, '', 'name', (current) => ({
    ...(current as Record<string, unknown>),
    description: 'Full legal name',
  }));
  const nameNode = getProperty(modified, '', 'name') as { type?: string };
  if (nameNode.type !== 'string') {
    throw new Error(`Expected type "string", got "${nameNode.type}"`);
  }
});

runTest('updateProperty preserves original schema (immutable)', () => {
  updateProperty(testSchema, '', 'name', (current) => ({
    ...(current as Record<string, unknown>),
    description: 'Full legal name',
  }));
  const origNameNode = getProperty(testSchema, '', 'name') as { description?: string };
  if (origNameNode.description === 'Full legal name') {
    throw new Error('Expected original schema to be unchanged');
  }
});

runTest('updateProperty adds constraint to existing property', () => {
  const modified = updateProperty(testSchema, '', 'age', (current) => ({
    ...(current as Record<string, unknown>),
    maximum: 120,
  }));
  const ageNode = getProperty(modified, '', 'age') as { maximum?: number; minimum?: number };
  if (ageNode.maximum !== 120) {
    throw new Error(`Expected maximum 120, got ${ageNode.maximum}`);
  }
  if (ageNode.minimum !== 0) {
    throw new Error(`Expected minimum 0, got ${ageNode.minimum}`);
  }
});

runTest('updateProperty adds custom attributes to scalar node', () => {
  const modified = updateProperty(testSchema, '', 'name', (current) => ({
    ...(current as Record<string, unknown>),
    'x-custom-field': 'custom value',
    'x-validation-rule': 'email-format',
  }));

  const nameNode = getProperty(modified, '', 'name') as Record<string, unknown>;
  if (nameNode['x-custom-field'] !== 'custom value') {
    throw new Error(`Expected x-custom-field "custom value", got "${nameNode['x-custom-field']}"`);
  }
  if (nameNode['x-validation-rule'] !== 'email-format') {
    throw new Error(`Expected x-validation-rule "email-format", got "${nameNode['x-validation-rule']}"`);
  }
  if ((nameNode.type as string) !== 'string') {
    throw new Error(`Expected type "string", got "${nameNode.type}"`);
  }
});

runTest('deleteProperty removes specified property', () => {
  const modified = deleteProperty(testSchema, '', 'email');
  if (hasProperty(modified, '', 'email')) {
    throw new Error('Expected email property to be removed');
  }
});

runTest('deleteProperty preserves original schema (immutable)', () => {
  deleteProperty(testSchema, '', 'email');
  if (!hasProperty(testSchema, '', 'email')) {
    throw new Error('Expected original schema to still have email property');
  }
});

runTest('deleteProperty preserves other properties', () => {
  const modified = deleteProperty(testSchema, '', 'email');
  if (!hasProperty(modified, '', 'name')) {
    throw new Error('Expected name property to still exist');
  }
  if (!hasProperty(modified, '', 'age')) {
    throw new Error('Expected age property to still exist');
  }
});

runTest('deleteProperty works with nested properties', () => {
  const modified = deleteProperty(testSchema, '/address', 'city');
  if (hasProperty(modified, '/address', 'city')) {
    throw new Error('Expected city property to be removed');
  }
  if (!hasProperty(modified, '/address', 'street')) {
    throw new Error('Expected street property to still exist');
  }
});

/* ========================================================================
   PUBLIC API - SPECIALIZED MUTATIONS
   ======================================================================== */

runTest('addProperty adds new property to root', () => {
  const modified = addProperty(testSchema, '', 'newField', {
    type: 'string',
    description: 'A new field',
  });
  if (!hasProperty(modified, '', 'newField')) {
    throw new Error('Expected newField property to exist');
  }
});

runTest('addProperty new property has correct schema', () => {
  const modified = addProperty(testSchema, '', 'newField', {
    type: 'string',
    description: 'A new field',
  });
  const newFieldNode = getProperty(modified, '', 'newField') as { type?: string; description?: string };
  if (newFieldNode.type !== 'string') {
    throw new Error(`Expected type "string", got "${newFieldNode.type}"`);
  }
  if (newFieldNode.description !== 'A new field') {
    throw new Error(`Expected description "A new field", got "${newFieldNode.description}"`);
  }
});

runTest('addProperty preserves original schema (immutable)', () => {
  addProperty(testSchema, '', 'newField', {
    type: 'string',
    description: 'A new field',
  });
  if (hasProperty(testSchema, '', 'newField')) {
    throw new Error('Expected original schema to not have newField property');
  }
});

runTest('addProperty adds property to nested object', () => {
  const modified = addProperty(testSchema, '/address', 'state', {
    type: 'string',
  });
  if (!hasProperty(modified, '/address', 'state')) {
    throw new Error('Expected state property to exist');
  }
});

runTest('addProperty creates properties object if missing', () => {
  const schema: JSONSchema = { type: 'object' };
  const modified = addProperty(schema, '', 'field', { type: 'string' });
  if (!hasProperty(modified, '', 'field')) {
    throw new Error('Expected field property to exist');
  }
});

runTest('renameProperty removes old property name', () => {
  const modified = renameProperty(testSchema, '', 'email', 'emailAddress');
  if (hasProperty(modified, '', 'email')) {
    throw new Error('Expected email property to be removed');
  }
});

runTest('renameProperty adds new property name', () => {
  const modified = renameProperty(testSchema, '', 'email', 'emailAddress');
  if (!hasProperty(modified, '', 'emailAddress')) {
    throw new Error('Expected emailAddress property to exist');
  }
});

runTest('renameProperty preserves property schema', () => {
  const modified = renameProperty(testSchema, '', 'email', 'emailAddress');
  const emailNode = getProperty(modified, '', 'emailAddress') as { format?: string };
  if (emailNode.format !== 'email') {
    throw new Error(`Expected format "email", got "${emailNode.format}"`);
  }
});

runTest('renameProperty works with nested properties', () => {
  const modified = renameProperty(testSchema, '/address', 'zipCode', 'postalCode');
  if (hasProperty(modified, '/address', 'zipCode')) {
    throw new Error('Expected zipCode property to be removed');
  }
  if (!hasProperty(modified, '/address', 'postalCode')) {
    throw new Error('Expected postalCode property to exist');
  }
});

runTest('renameProperty returns same schema if old and new names are identical', () => {
  const modified = renameProperty(testSchema, '', 'email', 'email');
  if (modified !== testSchema) {
    throw new Error('Expected same schema reference when names are identical');
  }
});

runTest('cloneProperty preserves original property', () => {
  const modified = cloneProperty(testSchema, '', 'name', '', 'fullName');
  if (!hasProperty(modified, '', 'name')) {
    throw new Error('Expected name property to still exist');
  }
});

runTest('cloneProperty creates cloned property', () => {
  const modified = cloneProperty(testSchema, '', 'name', '', 'fullName');
  if (!hasProperty(modified, '', 'fullName')) {
    throw new Error('Expected fullName property to exist');
  }
});

runTest('cloneProperty clone has same schema as original', () => {
  const modified = cloneProperty(testSchema, '', 'name', '', 'fullName');
  const fullNameNode = getProperty(modified, '', 'fullName') as { type?: string; description?: string };
  const nameNode = getProperty(modified, '', 'name') as { type?: string; description?: string };
  if (fullNameNode.type !== nameNode.type) {
    throw new Error(`Expected same type, got ${fullNameNode.type} vs ${nameNode.type}`);
  }
  if (fullNameNode.description !== nameNode.description) {
    throw new Error(`Expected same description, got ${fullNameNode.description} vs ${nameNode.description}`);
  }
});

runTest('cloneProperty works across different parent objects', () => {
  const modified = cloneProperty(testSchema, '', 'email', '/address', 'contactEmail');
  if (!hasProperty(modified, '', 'email')) {
    throw new Error('Expected email property to still exist');
  }
  if (!hasProperty(modified, '/address', 'contactEmail')) {
    throw new Error('Expected contactEmail property to exist');
  }
});

runTest('moveProperty removes property from original location', () => {
  const modified = moveProperty(testSchema, '', 'email', '/address', 'email');
  if (hasProperty(modified, '', 'email')) {
    throw new Error('Expected email property to be removed from root');
  }
});

runTest('moveProperty adds property to new location', () => {
  const modified = moveProperty(testSchema, '', 'email', '/address', 'email');
  if (!hasProperty(modified, '/address', 'email')) {
    throw new Error('Expected email property to exist in address');
  }
});

runTest('moveProperty preserves property schema', () => {
  const modified = moveProperty(testSchema, '', 'email', '/address', 'email');
  const movedEmailNode = getProperty(modified, '/address', 'email') as { format?: string };
  if (movedEmailNode.format !== 'email') {
    throw new Error(`Expected format "email", got "${movedEmailNode.format}"`);
  }
});

runTest('moveProperty allows renaming during move', () => {
  const modified = moveProperty(testSchema, '', 'email', '/address', 'contactEmail');
  if (hasProperty(modified, '', 'email')) {
    throw new Error('Expected email property to be removed from root');
  }
  if (!hasProperty(modified, '/address', 'contactEmail')) {
    throw new Error('Expected contactEmail property to exist');
  }
});

/* ========================================================================
   INTEGRATION & EDGE CASES
   ======================================================================== */

runTest('builds nested object structure', () => {
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

  if (!hasProperty(schema, '', 'settings')) {
    throw new Error('Expected settings property to exist');
  }
  if (!hasProperty(schema, '/settings', 'locale')) {
    throw new Error('Expected locale property to exist');
  }
  if (!hasProperty(schema, '/settings', 'timezone')) {
    throw new Error('Expected timezone property to exist');
  }
});

runTest('reorganizes schema structure', () => {
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

  if (hasProperty(schema, '/settings', 'locale')) {
    throw new Error('Expected locale property to be removed');
  }
  if (!hasProperty(schema, '/settings', 'language')) {
    throw new Error('Expected language property to exist');
  }
  if (hasProperty(schema, '/settings', 'timezone')) {
    throw new Error('Expected timezone property to be removed from settings');
  }
  if (!hasProperty(schema, '', 'timezone')) {
    throw new Error('Expected timezone property to exist at root');
  }
});

runTest('performs complex query and mutation workflow', () => {
  let schema = testSchema;
  schema = addProperty(schema, '', 'settings', {
    type: 'object',
    properties: {},
  });

  const allObjects = findNodes(schema, (node) => node.kind === 'object');
  if (allObjects.length === 0) {
    throw new Error('Expected to find at least one object node');
  }

  // Add metadata to all string properties
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
  if (validatedCount === 0) {
    throw new Error('Expected at least one validated property');
  }
});

runTest('adds custom properties to all attributes in nested object', () => {
  let schema = testSchema;

  // Get all children of the address object
  const addressChildren = getChildren(schema, '/address');
  if (addressChildren.length === 0) {
    throw new Error('Expected at least one child');
  }

  // Add custom attributes to all sub-properties of address
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

  // Verify all address properties have the custom attributes
  const updatedChildren = getChildren(schema, '/address');
  updatedChildren.forEach((child) => {
    if (child.key !== null) {
      const childSchema = getProperty(schema, '/address', child.key) as Record<string, unknown>;
      if (childSchema['x-required-level'] !== 'high') {
        throw new Error(`Expected x-required-level "high", got "${childSchema['x-required-level']}"`);
      }
      if (childSchema['x-pii'] !== true) {
        throw new Error(`Expected x-pii true, got ${childSchema['x-pii']}`);
      }
      if (childSchema['x-category'] !== 'address-component') {
        throw new Error(`Expected x-category "address-component", got "${childSchema['x-category']}"`);
      }

      // Verify original schema properties are preserved
      if (childSchema.type === undefined) {
        throw new Error('Expected type to be preserved');
      }
    }
  });

  // Verify other properties weren't affected
  const nameSchema = getProperty(schema, '', 'name') as Record<string, unknown>;
  if (nameSchema['x-pii'] !== undefined) {
    throw new Error('Expected name property not to have x-pii attribute');
  }
});

runTest('handles minimal scalar schema', () => {
  const minimalSchema: JSONSchema = {
    type: 'string',
  };

  const minimalIndex = buildIndex(minimalSchema);
  if (minimalIndex.size !== 1) {
    throw new Error(`Expected index size 1, got ${minimalIndex.size}`);
  }
  const rootNode = minimalIndex.get('');
  if (!rootNode) {
    throw new Error('Expected root node to exist');
  }
  if (rootNode.kind !== 'scalar') {
    throw new Error(`Expected kind "scalar", got "${rootNode.kind}"`);
  }
});

runTest('handles empty object schema', () => {
  const emptyObjectSchema: JSONSchema = {
    type: 'object',
    properties: {},
  };

  const emptyIndex = buildIndex(emptyObjectSchema);
  if (emptyIndex.size !== 1) {
    throw new Error(`Expected index size 1, got ${emptyIndex.size}`);
  }
  const rootNode = emptyIndex.get('');
  if (!rootNode) {
    throw new Error('Expected root node to exist');
  }
  if (rootNode.kind !== 'object') {
    throw new Error(`Expected kind "object", got "${rootNode.kind}"`);
  }

  const emptyChildren = getChildren(emptyObjectSchema, '');
  if (emptyChildren.length !== 0) {
    throw new Error(`Expected empty children array, got ${emptyChildren.length}`);
  }
});

runTest('adds property to empty object schema', () => {
  const emptyObjectSchema: JSONSchema = {
    type: 'object',
    properties: {},
  };

  const withProperty = addProperty(emptyObjectSchema, '', 'newField', { type: 'string' });
  if (!hasProperty(withProperty, '', 'newField')) {
    throw new Error('Expected newField property to exist');
  }
});

runTest('handles deeply nested array schema', () => {
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
  if (nestedIndex.size !== 1) {
    throw new Error(`Expected index size 1, got ${nestedIndex.size}`);
  }

  const level1Children = getChildren(nestedArraySchema, '');
  if (level1Children.length !== 0) {
    throw new Error(`Expected empty children array, got ${level1Children.length}`);
  }
});

runTest('handles schema without type field', () => {
  const schemaWithoutType: JSONSchema = {
    properties: {
      field: { type: 'string' },
    },
  };

  const index = buildIndex(schemaWithoutType);
  if (index.size === 0) {
    throw new Error('Expected at least one node in index');
  }
  const rootNode = index.get('');
  if (!rootNode) {
    throw new Error('Expected root node to exist');
  }
  if (rootNode.kind !== 'object') {
    throw new Error(`Expected kind "object", got "${rootNode.kind}"`);
  }
});

runTest('handles schema with only items (implicit array)', () => {
  const implicitArray: JSONSchema = {
    items: { type: 'string' },
  };

  const index = buildIndex(implicitArray);
  const rootNode = index.get('');
  if (!rootNode) {
    throw new Error('Expected root node to exist');
  }
  if (rootNode.kind !== 'array') {
    throw new Error(`Expected kind "array", got "${rootNode.kind}"`);
  }
});

// eslint-disable-next-line no-console
console.log('\n🎉 All tests completed!');
