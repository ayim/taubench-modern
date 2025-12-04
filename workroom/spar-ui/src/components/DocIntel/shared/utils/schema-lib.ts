/* eslint-disable import/no-extraneous-dependencies */
/**
 * JSON Schema Traversal & Mutation Library
 *
 * A self-contained library for traversing, indexing, and mutating JSON Schema documents.
 * Supports properties (objects) and items (arrays) traversal with immutable mutations.
 *
 * Dependencies:
 *   - jsonpointer: ^5.0.1
 *   - lodash.clonedeep: ^4.5.0
 *   - @types/jsonpointer: ^5.0.2 (dev)
 */

import * as jsonpointer from 'jsonpointer';
import cloneDeep from 'lodash.clonedeep';

/* ========================================================================
   1. PUBLIC TYPE DEFINITIONS
   ======================================================================== */

/**
 * A JSON Schema node (flexible type to accommodate any schema structure)
 */
export type JSONSchema = {
  [key: string]: unknown;
};

/**
 * The kind of schema node
 * - object: has properties or type "object"
 * - array: has items or type "array"
 * - scalar: everything else (primitives, etc.)
 */
export type SchemaNodeKind = 'object' | 'array' | 'scalar';

/**
 * A node in the schema tree with metadata
 */
export interface SchemaNode {
  /** JSON Pointer path for this node (e.g. "" for root, "/properties/name" for property) */
  pointer: string;
  /** Parent pointer (null for root) */
  parentPointer: string | null;
  /** Property name or "items" for arrays; null for root */
  key: string | null;
  /** The schema node itself */
  schema: JSONSchema;
  /** The kind of node */
  kind: SchemaNodeKind;
}

/**
 * Index mapping JSON Pointer paths to schema nodes
 */
export type SchemaIndex = Map<string, SchemaNode>;

/**
 * Visitor callback for schema traversal
 */
export type SchemaVisitor = (node: SchemaNode) => void;

/**
 * Predicate function for finding nodes
 */
export type SchemaNodePredicate = (node: SchemaNode) => boolean;

/**
 * Updater function for node mutations
 */
export type NodeUpdater<T = JSONSchema> = (current: T | undefined) => T;

/* ========================================================================
   2. POINTER UTILITIES (used by internal functions)

   These functions are exported and used internally by the library.
   They handle JSON Pointer path conversion and token escaping.
   ======================================================================== */

/**
 * Escape a single JSON Pointer token according to RFC 6901
 * ~ becomes ~0
 * / becomes ~1
 */
export function escapePointerToken(token: string): string {
  return token.replace(/~/g, '~0').replace(/\//g, '~1');
}

/**
 * Unescape a single JSON Pointer token according to RFC 6901
 * ~1 becomes /
 * ~0 becomes ~
 */
export function unescapePointerToken(token: string): string {
  return token.replace(/~1/g, '/').replace(/~0/g, '~');
}

/**
 * Convert a JSON Pointer to an array of path tokens
 * Example: "/user/name" -> ["user", "name"]
 */
export function pointerToPath(pointer: string): string[] {
  if (pointer === '') return [];
  if (!pointer.startsWith('/')) {
    throw new Error(`Invalid JSON Pointer: must start with / or be empty string`);
  }
  return pointer.slice(1).split('/').map(unescapePointerToken);
}

/**
 * Convert an array of path tokens to a JSON Pointer
 * Example: ["user", "name"] -> "/user/name"
 */
export function pathToPointer(path: string[]): string {
  if (path.length === 0) return '';
  return `/${path.map(escapePointerToken).join('/')}`;
}

/* ========================================================================
   3. INTERNAL HELPER FUNCTIONS

   These functions are not exported and are used internally by the library.
   They handle low-level operations like path conversion and direct schema
   manipulation using JSON Pointers.
   ======================================================================== */

/**
 * Determine the kind of a schema node
 * @internal
 */
function getNodeKind(node: JSONSchema): SchemaNodeKind {
  if (!node || typeof node !== 'object') return 'scalar';
  if (node.type === 'object' || node.properties) return 'object';
  if (node.type === 'array' || node.items) return 'array';
  return 'scalar';
}

/**
 * Get the schema node at a specific JSON Pointer.
 * Returns undefined if the pointer doesn't exist.
 * @internal
 */
function getNode(schema: JSONSchema, pointer: string): JSONSchema | undefined {
  try {
    return jsonpointer.get(schema, pointer);
  } catch (e) {
    return undefined;
  }
}

/**
 * Check if a node exists at the given pointer
 * @internal
 */
function hasNode(schema: JSONSchema, pointer: string): boolean {
  return getNode(schema, pointer) !== undefined;
}

/**
 * Set a node at a specific pointer to a new value (immutable).
 * Returns a new schema with the change applied.
 * @internal
 */
function setNode(schema: JSONSchema, pointer: string, value: JSONSchema): JSONSchema {
  const copy = cloneDeep(schema);
  jsonpointer.set(copy, pointer, value);
  return copy;
}

/**
 * Update a node at a specific pointer using an updater function (immutable).
 * The updater receives the current value (or undefined) and returns the new value.
 * Returns a new schema with the change applied.
 * @internal
 */
function updateNode<T = JSONSchema>(schema: JSONSchema, pointer: string, updater: NodeUpdater<T>): JSONSchema {
  const copy = cloneDeep(schema);
  const current = jsonpointer.get(copy, pointer) as T | undefined;
  const next = updater(current);
  jsonpointer.set(copy, pointer, next);
  return copy;
}

/**
 * Delete a node at a specific pointer (immutable).
 * For properties, removes the property from its parent object.
 * For items, this is not typically meaningful but will attempt removal.
 * Returns a new schema with the node removed.
 * @internal
 */
function deleteNode(schema: JSONSchema, pointer: string): JSONSchema {
  if (pointer === '') {
    throw new Error('Cannot delete root node');
  }

  const path = pointerToPath(pointer);
  if (path.length < 2) {
    throw new Error('Cannot delete node: invalid pointer structure');
  }

  const copy = cloneDeep(schema);

  // Get parent object/array and the key to delete
  const parentPath = path.slice(0, -1);
  const keyToDelete = path[path.length - 1];
  const parentPointer = pathToPointer(parentPath);

  const parent = jsonpointer.get(copy, parentPointer);
  if (!parent || typeof parent !== 'object') {
    throw new Error(`Cannot delete: parent at ${parentPointer} is not an object`);
  }

  // Delete the key
  delete parent[keyToDelete];

  return copy;
}

/**
 * Build a property path from an object pointer and property name.
 * Handles both root-level properties (objectPointer === '') and nested properties.
 * @internal
 */
function buildPropertyPath(objectPointer: string, propertyName: string): string {
  return objectPointer === ''
    ? `/properties/${escapePointerToken(propertyName)}`
    : `${objectPointer}/properties/${escapePointerToken(propertyName)}`;
}

/**
 * Validate that an object pointer is not a scalar (scalars cannot have properties).
 * Throws an error if the pointer points to a scalar value.
 * Used for read operations that allow undefined nodes.
 * @internal
 */
function validateNotScalar(schema: JSONSchema, objectPointer: string): void {
  if (objectPointer !== '') {
    const parentNode = getNode(schema, objectPointer);
    if (parentNode && getNodeKind(parentNode) === 'scalar') {
      throw new Error(`Invalid path: cannot navigate into scalar value at "${objectPointer}"`);
    }
  }
}

/**
 * Validate that an object pointer exists and points to an object (not scalar, array, or undefined).
 * Throws an error if the node doesn't exist or is not an object.
 * Used for write operations that require the node to exist.
 * @internal
 */
function validateIsObject(schema: JSONSchema, objectPointer: string): void {
  const objectNode = getNode(schema, objectPointer);
  if (!objectNode || typeof objectNode !== 'object') {
    throw new Error(`Node at ${objectPointer} is not an object`);
  }
  if (getNodeKind(objectNode) === 'scalar') {
    throw new Error(`Invalid path: cannot navigate into scalar value at "${objectPointer}"`);
  }
}

/* ========================================================================
   4. PUBLIC API - TRAVERSAL
   ======================================================================== */

/**
 * Walk a JSON Schema in depth-first order, calling the visitor for each node.
 * Traverses properties (for objects) and items (for arrays).
 * Node pointers are returned as JSON Pointer paths (e.g., "/properties/address/properties/city").
 */
export function walk(schema: JSONSchema, visitor: SchemaVisitor): void {
  function recurse(node: JSONSchema, pointer: string, parentPointer: string | null, key: string | null): void {
    const kind = getNodeKind(node);

    const schemaNode: SchemaNode = {
      pointer,
      parentPointer,
      key,
      schema: node,
      kind,
    };

    visitor(schemaNode);

    // Traverse object properties
    if (kind === 'object' && node.properties && typeof node.properties === 'object') {
      Object.entries(node.properties as Record<string, JSONSchema>).forEach(([propName, propSchema]) => {
        const childPointer = `${pointer}/properties/${escapePointerToken(propName)}`;
        recurse(propSchema, childPointer, pointer, propName);
      });
    }

    // Traverse array items
    if (kind === 'array' && node.items && typeof node.items === 'object') {
      const itemsPointer = `${pointer}/items`;
      recurse(node.items as JSONSchema, itemsPointer, pointer, 'items');
    }
  }

  recurse(schema, '', null, null);
}

/**
 * Validates a single schema node.
 * @internal
 */
function validateSchemaNode(node: SchemaNode): void {
  const nodeSchema = node.schema as { type?: string; properties?: unknown; items?: unknown };

  if (node.kind === 'object') {
    if (nodeSchema.type === 'object' && !nodeSchema.properties) {
      throw new Error(
        `Schema validation failed: object at "${node.pointer}" has type="object" but missing 'properties' attribute`,
      );
    }
  } else if (node.kind === 'array') {
    if (nodeSchema.type === 'array' && !nodeSchema.items) {
      throw new Error(
        `Schema validation failed: array at "${node.pointer}" has type="array" but missing 'items' attribute`,
      );
    }
  }
}

/**
 * Build an index of all schema nodes keyed by their JSON Pointer path.
 */
export function buildIndex(schema: JSONSchema): SchemaIndex {
  const index = new Map<string, SchemaNode>();
  walk(schema, (node) => {
    index.set(node.pointer, node);
  });
  return index;
}

/* ========================================================================
   5. PUBLIC API - QUERY OPERATIONS
   ======================================================================== */

/**
 * Validate that a JSON Schema is well-formed.
 * Uses the `walk` function to traverse the schema and ensure all type=object nodes
 * have 'properties' and all type=array nodes have 'items'.
 *
 * This is a tool for callers to validate schemas upfront before using other operations.
 * Once validated, operations can assume the schema is well-formed.
 *
 * @param schema The JSON Schema to validate
 * @throws {Error} If the schema is malformed (missing required attributes)
 *
 * @example
 * // Validate schema when received from API or user input
 * try {
 *   validateSchema(schema);
 *   // Schema is well-formed, safe to use with other operations
 *   getProperty(schema, '', 'name');
 * } catch (error) {
 *   // Handle malformed schema
 * }
 */
export function validateSchema(schema: JSONSchema): void {
  walk(schema, validateSchemaNode);
}

/**
 * Find all nodes matching a predicate function
 */
export function findNodes(schema: JSONSchema, predicate: SchemaNodePredicate): SchemaNode[] {
  const matches: SchemaNode[] = [];
  walk(schema, (node) => {
    if (predicate(node)) {
      matches.push(node);
    }
  });
  return matches;
}

/**
 * Get the direct children of a node at the given JSON Pointer path.
 * For objects, returns child nodes from properties.
 * For arrays, returns child nodes from items.
 * For scalars, returns an empty array.
 *
 * @param pointer JSON Pointer path (e.g., "/properties/address")
 */
export function getChildren(schema: JSONSchema, pointer: string): SchemaNode[] {
  const node = getNode(schema, pointer);
  if (!node) return [];

  const kind = getNodeKind(node);
  const children: SchemaNode[] = [];

  if (kind === 'object' && node.properties && typeof node.properties === 'object') {
    Object.entries(node.properties as Record<string, JSONSchema>).forEach(([propName, propSchema]) => {
      const childPointer = `${pointer}/properties/${escapePointerToken(propName)}`;
      children.push({
        pointer: childPointer,
        parentPointer: pointer,
        key: propName,
        schema: propSchema,
        kind: getNodeKind(propSchema),
      });
    });
  }

  if (kind === 'array' && node.items && typeof node.items === 'object') {
    const itemsPointer = `${pointer}/items`;
    const itemsSchema = node.items as JSONSchema;
    children.push({
      pointer: itemsPointer,
      parentPointer: pointer,
      key: 'items',
      schema: itemsSchema,
      kind: getNodeKind(itemsSchema),
    });
  }

  return children;
}

/**
 * Get the parent node of the node at the given JSON Pointer path.
 * Returns undefined if the node is the root or doesn't exist.
 *
 * @param pointer JSON Pointer path (e.g., "/properties/address/properties/city")
 */
export function getParent(schema: JSONSchema, pointer: string): SchemaNode | undefined {
  if (pointer === '') return undefined; // root has no parent

  const path = pointerToPath(pointer);
  if (path.length < 2) return undefined; // need at least 2 segments to have a meaningful parent

  // Properties add 2 segments (/properties/name), so parent is 2 segments up
  // Array items add 1 segment (/items), so parent is 1 segment up
  const isArrayItem = path[path.length - 1] === 'items';
  const segmentsToGoUp = isArrayItem ? 1 : 2;
  const parentPath = path.slice(0, -segmentsToGoUp);
  const parentPointer = pathToPointer(parentPath);

  const parentSchema = getNode(schema, parentPointer);
  if (!parentSchema) return undefined;

  return {
    pointer: parentPointer,
    parentPointer: parentPath.length >= 2 ? pathToPointer(parentPath.slice(0, -2)) : null,
    key: parentPath.length > 0 ? parentPath[parentPath.length - 1] : null,
    schema: parentSchema,
    kind: getNodeKind(parentSchema),
  };
}

/* ========================================================================
   6. PUBLIC API - PROPERTY OPERATIONS
   ======================================================================== */

/**
 * Get a property schema by name from an object (convenience wrapper).
 *
 * @param objectPointer JSON Pointer path to the parent object (e.g., "" for root, "/properties/address" for nested)
 * @param propertyName Name of the property
 *
 * @example
 * getProperty(schema, "", "name") // Gets the "name" property from root
 * getProperty(schema, "/properties/address", "city") // Gets the "city" property from address
 */
export function getProperty(schema: JSONSchema, objectPointer: string, propertyName: string): JSONSchema | undefined {
  validateNotScalar(schema, objectPointer);
  const propertyPath = buildPropertyPath(objectPointer, propertyName);
  return getNode(schema, propertyPath);
}

/**
 * Check if a property exists in an object (convenience wrapper).
 *
 * @param objectPointer JSON Pointer path to the parent object (e.g., "" for root, "/properties/address" for nested)
 * @param propertyName Name of the property
 *
 * @example
 * hasProperty(schema, "", "name") // Check if root has "name" property
 */
export function hasProperty(schema: JSONSchema, objectPointer: string, propertyName: string): boolean {
  validateNotScalar(schema, objectPointer);
  const propertyPath = buildPropertyPath(objectPointer, propertyName);
  return hasNode(schema, propertyPath);
}

/**
 * Set a property schema by name (convenience wrapper).
 *
 * @param objectPointer JSON Pointer path to the parent object (e.g., "" for root, "/properties/address" for nested)
 * @param propertyName Name of the property
 * @param propertySchema The schema to set for the property
 *
 * @example
 * setProperty(schema, "", "name", { type: "string", minLength: 1 })
 */
export function setProperty(
  schema: JSONSchema,
  objectPointer: string,
  propertyName: string,
  propertySchema: JSONSchema,
): JSONSchema {
  validateNotScalar(schema, objectPointer);
  const propertyPath = buildPropertyPath(objectPointer, propertyName);
  return setNode(schema, propertyPath, propertySchema);
}

/**
 * Update a property schema by name using an updater function (convenience wrapper).
 *
 * @param objectPointer JSON Pointer path to the parent object (e.g., "" for root, "/properties/address" for nested)
 * @param propertyName Name of the property
 * @param updater Function that receives current schema and returns updated schema
 *
 * @example
 * updateProperty(schema, "", "name", (current) => ({ ...current, description: "Full name" }))
 */
export function updateProperty<T = JSONSchema>(
  schema: JSONSchema,
  objectPointer: string,
  propertyName: string,
  updater: NodeUpdater<T>,
): JSONSchema {
  validateNotScalar(schema, objectPointer);
  const propertyPath = buildPropertyPath(objectPointer, propertyName);
  return updateNode(schema, propertyPath, updater);
}

/**
 * Delete a property by name (convenience wrapper).
 *
 * @param objectPointer JSON Pointer path to the parent object (e.g., "" for root, "/properties/address" for nested)
 * @param propertyName Name of the property to delete
 *
 * @example
 * deleteProperty(schema, "", "obsoleteField")
 */
export function deleteProperty(schema: JSONSchema, objectPointer: string, propertyName: string): JSONSchema {
  validateNotScalar(schema, objectPointer);
  const propertyPath = buildPropertyPath(objectPointer, propertyName);
  return deleteNode(schema, propertyPath);
}

/* ========================================================================
   7. PUBLIC API - SPECIALIZED MUTATIONS
   ======================================================================== */

/**
 * Add a property to an object schema (immutable).
 * Returns a new schema with the property added.
 *
 * @param objectPointer JSON Pointer path to the parent object (e.g., "" for root, "/properties/address" for nested)
 * @param propertyName Name of the property to add
 * @param propertySchema Schema for the new property
 */
export function addProperty(
  schema: JSONSchema,
  objectPointer: string,
  propertyName: string,
  propertySchema: JSONSchema,
): JSONSchema {
  validateIsObject(schema, objectPointer);
  const copy = cloneDeep(schema);
  const objectNode = jsonpointer.get(copy, objectPointer);

  // Ensure properties object exists
  if (!objectNode.properties) {
    objectNode.properties = {};
  }

  // Add the property
  objectNode.properties[propertyName] = propertySchema;

  return copy;
}

/**
 * Rename a property in an object schema (immutable).
 * Returns a new schema with the property renamed.
 *
 * @param objectPointer JSON Pointer path to the parent object (e.g., "" for root, "/properties/address" for nested)
 * @param oldName Current name of the property
 * @param newName New name for the property
 */
export function renameProperty(
  schema: JSONSchema,
  objectPointer: string,
  oldName: string,
  newName: string,
): JSONSchema {
  if (oldName === newName) {
    return schema; // no change needed
  }

  validateIsObject(schema, objectPointer);
  const copy = cloneDeep(schema);
  const parentNode = jsonpointer.get(copy, objectPointer);

  if (!parentNode.properties) {
    throw new Error(`Object at ${objectPointer} has no properties`);
  }

  // Get the property schema
  const propSchema = parentNode.properties[oldName];
  if (!propSchema) {
    throw new Error(`Property ${oldName} not found at ${objectPointer}`);
  }

  // Rename: add new, delete old
  parentNode.properties[newName] = propSchema;
  delete parentNode.properties[oldName];

  return copy;
}

/**
 * Move a property from one location to another (immutable).
 * Returns a new schema with the property moved.
 *
 * @param fromObjectPointer JSON Pointer path to the source parent object
 * @param propertyName Name of the property to move
 * @param toObjectPointer JSON Pointer path to the target parent object
 * @param newPropertyName Name for the property in the new location
 */
export function moveProperty(
  schema: JSONSchema,
  fromObjectPointer: string,
  propertyName: string,
  toObjectPointer: string,
  newPropertyName: string,
): JSONSchema {
  // Get the property schema to move
  const propSchema = getProperty(schema, fromObjectPointer, propertyName);
  if (!propSchema) {
    throw new Error(`Source property ${propertyName} not found at ${fromObjectPointer}`);
  }

  // Clone it to the new location
  let copy = addProperty(schema, toObjectPointer, newPropertyName, propSchema);

  // Delete from old location
  copy = deleteProperty(copy, fromObjectPointer, propertyName);

  return copy;
}

/**
 * Clone (copy) a property from one location to another (immutable).
 * Returns a new schema with the property cloned.
 *
 * @param fromObjectPointer JSON Pointer path to the source parent object
 * @param propertyName Name of the property to clone
 * @param toObjectPointer JSON Pointer path to the target parent object
 * @param newPropertyName Name for the property in the new location
 */
export function cloneProperty(
  schema: JSONSchema,
  fromObjectPointer: string,
  propertyName: string,
  toObjectPointer: string,
  newPropertyName: string,
): JSONSchema {
  // Get the property schema to clone
  const propSchema = getProperty(schema, fromObjectPointer, propertyName);
  if (!propSchema) {
    throw new Error(`Source property ${propertyName} not found at ${fromObjectPointer}`);
  }

  // Add it to the new location (addProperty already does deep cloning)
  return addProperty(schema, toObjectPointer, newPropertyName, propSchema);
}
