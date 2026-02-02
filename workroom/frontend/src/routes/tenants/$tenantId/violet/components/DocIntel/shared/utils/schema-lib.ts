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
  /** Logical path for this node (e.g. "" for root, "/name" for property) */
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
 * Index mapping logical paths to schema nodes
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
 * Convert a logical path to an internal JSON Pointer path.
 * Logical paths use simplified notation without /properties/ or /items/.
 *
 * Examples:
 *   "" -> ""
 *   "/name" -> "/properties/name"
 *   "/address/city" -> "/properties/address/properties/city"
 *   "/tags" -> "/properties/tags" (array itself, not items)
 *
 * @internal
 */
function logicalToInternal(logicalPath: string): string {
  if (logicalPath === '') return '';

  const tokens = pointerToPath(logicalPath);
  const internalTokens = tokens.flatMap((token) => ['properties', token]);

  return pathToPointer(internalTokens);
}

/**
 * Convert an internal JSON Pointer path to a logical path.
 * Removes /properties/ and /items/ segments to create simplified notation.
 *
 * Examples:
 *   "" -> ""
 *   "/properties/name" -> "/name"
 *   "/properties/address/properties/city" -> "/address/city"
 *   "/properties/tags/items" -> "/tags" (array itself)
 *
 * @internal
 */
function internalToLogical(internalPath: string): string {
  if (internalPath === '') return '';

  const tokens = pointerToPath(internalPath);
  const logicalTokens = tokens.filter((token) => token !== 'properties' && token !== 'items');

  return pathToPointer(logicalTokens);
}

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

/* ========================================================================
   4. PUBLIC API - TRAVERSAL
   ======================================================================== */

/**
 * Walk a JSON Schema in depth-first order, calling the visitor for each node.
 * Traverses properties (for objects). Array items are not traversed as separate nodes
 * since they are implicit in the array's schema.
 * Node pointers are returned in logical format (e.g., "/address/city" not "/properties/address/properties/city").
 */
export function walk(schema: JSONSchema, visitor: SchemaVisitor): void {
  function recurse(
    node: JSONSchema,
    internalPointer: string,
    internalParentPointer: string | null,
    key: string | null,
  ): void {
    const kind = getNodeKind(node);

    // Convert internal pointers to logical format for the visitor
    const schemaNode: SchemaNode = {
      pointer: internalToLogical(internalPointer),
      parentPointer: internalParentPointer !== null ? internalToLogical(internalParentPointer) : null,
      key,
      schema: node,
      kind,
    };

    visitor(schemaNode);

    // Traverse object properties
    if (kind === 'object' && node.properties && typeof node.properties === 'object') {
      Object.entries(node.properties as Record<string, JSONSchema>).forEach(([propName, propSchema]) => {
        const childPointer = `${internalPointer}/properties/${escapePointerToken(propName)}`;
        recurse(propSchema, childPointer, internalPointer, propName);
      });
    }

    // Note: We do NOT traverse into array items as separate nodes.
    // Array items are implicit in the array node and can be accessed via node.schema.items
  }

  recurse(schema, '', null, null);
}

/**
 * Build an index of all schema nodes keyed by their logical path.
 * Logical paths use simplified notation without /properties/ or /items/.
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
 * Get the direct children of a node at the given logical path.
 * For objects, returns child nodes from properties.
 * For arrays, returns an empty array (items are implicit, not separate nodes).
 * For scalars, returns an empty array.
 *
 * @param pointer Logical path (e.g., "/address" not "/properties/address")
 */
export function getChildren(schema: JSONSchema, pointer: string): SchemaNode[] {
  const internalPointer = logicalToInternal(pointer);
  const node = getNode(schema, internalPointer);
  if (!node) return [];

  const kind = getNodeKind(node);
  const children: SchemaNode[] = [];

  if (kind === 'object' && node.properties && typeof node.properties === 'object') {
    Object.entries(node.properties as Record<string, JSONSchema>).forEach(([propName, propSchema]) => {
      const childInternalPointer = `${internalPointer}/properties/${escapePointerToken(propName)}`;
      children.push({
        pointer: internalToLogical(childInternalPointer),
        parentPointer: pointer,
        key: propName,
        schema: propSchema,
        kind: getNodeKind(propSchema),
      });
    });
  }

  // Note: Arrays do not have children in the logical model.
  // The items schema is implicit and can be accessed via node.schema.items

  return children;
}

/**
 * Get the parent node of the node at the given logical path.
 * Returns undefined if the node is the root or doesn't exist.
 *
 * @param pointer Logical path (e.g., "/address/city" not "/properties/address/properties/city")
 */
export function getParent(schema: JSONSchema, pointer: string): SchemaNode | undefined {
  if (pointer === '') return undefined; // root has no parent

  const internalPointer = logicalToInternal(pointer);
  const internalPath = pointerToPath(internalPointer);
  if (internalPath.length < 2) return undefined; // need at least 2 segments to have a meaningful parent

  // Parent is typically 2 segments up: /properties/foo -> ""
  const parentInternalPath = internalPath.slice(0, -2);
  const parentInternalPointer = pathToPointer(parentInternalPath);

  const parentSchema = getNode(schema, parentInternalPointer);
  if (!parentSchema) return undefined;

  return {
    pointer: internalToLogical(parentInternalPointer),
    parentPointer:
      parentInternalPath.length >= 2 ? internalToLogical(pathToPointer(parentInternalPath.slice(0, -2))) : null,
    key: parentInternalPath.length > 0 ? parentInternalPath[parentInternalPath.length - 1] : null,
    schema: parentSchema,
    kind: getNodeKind(parentSchema),
  };
}

/* ========================================================================
   6. PUBLIC API - PROPERTY OPERATIONS
   ======================================================================== */

/**
 * Build a logical path for a property within an object.
 * Convenience helper to avoid manual path construction.
 *
 * @param objectPointer Logical path to the parent object (e.g., "" for root, "/address" for nested)
 * @param propertyName Name of the property
 * @returns Logical path to the property
 *
 * @example
 * propertyPointer("", "name") → "/name"
 * propertyPointer("/address", "city") → "/address/city"
 */
export function propertyPointer(objectPointer: string, propertyName: string): string {
  if (objectPointer === '') {
    return `/${escapePointerToken(propertyName)}`;
  }
  return `${objectPointer}/${escapePointerToken(propertyName)}`;
}

/**
 * Get a property schema by name from an object (convenience wrapper).
 *
 * @param objectPointer Logical path to the parent object (e.g., "" for root, "/address" for nested)
 * @param propertyName Name of the property
 *
 * @example
 * getProperty(schema, "", "name") // Gets the "name" property from root
 * getProperty(schema, "/address", "city") // Gets the "city" property from address
 */
export function getProperty(schema: JSONSchema, objectPointer: string, propertyName: string): JSONSchema | undefined {
  const logicalPath = propertyPointer(objectPointer, propertyName);
  const internalPath = logicalToInternal(logicalPath);
  return getNode(schema, internalPath);
}

/**
 * Check if a property exists in an object (convenience wrapper).
 *
 * @param objectPointer Logical path to the parent object (e.g., "" for root, "/address" for nested)
 * @param propertyName Name of the property
 *
 * @example
 * hasProperty(schema, "", "name") // Check if root has "name" property
 */
export function hasProperty(schema: JSONSchema, objectPointer: string, propertyName: string): boolean {
  const logicalPath = propertyPointer(objectPointer, propertyName);
  const internalPath = logicalToInternal(logicalPath);
  return hasNode(schema, internalPath);
}

/**
 * Set a property schema by name (convenience wrapper).
 *
 * @param objectPointer Logical path to the parent object (e.g., "" for root, "/address" for nested)
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
  const logicalPath = propertyPointer(objectPointer, propertyName);
  const internalPath = logicalToInternal(logicalPath);
  return setNode(schema, internalPath, propertySchema);
}

/**
 * Update a property schema by name using an updater function (convenience wrapper).
 *
 * @param objectPointer Logical path to the parent object (e.g., "" for root, "/address" for nested)
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
  const logicalPath = propertyPointer(objectPointer, propertyName);
  const internalPath = logicalToInternal(logicalPath);
  return updateNode(schema, internalPath, updater);
}

/**
 * Delete a property by name (convenience wrapper).
 *
 * @param objectPointer Logical path to the parent object (e.g., "" for root, "/address" for nested)
 * @param propertyName Name of the property to delete
 *
 * @example
 * deleteProperty(schema, "", "obsoleteField")
 */
export function deleteProperty(schema: JSONSchema, objectPointer: string, propertyName: string): JSONSchema {
  const logicalPath = propertyPointer(objectPointer, propertyName);
  const internalPath = logicalToInternal(logicalPath);
  return deleteNode(schema, internalPath);
}

/* ========================================================================
   7. PUBLIC API - SPECIALIZED MUTATIONS
   ======================================================================== */

/**
 * Add a property to an object schema (immutable).
 * Returns a new schema with the property added.
 *
 * @param objectPointer Logical path to the parent object (e.g., "" for root, "/address" for nested)
 * @param propertyName Name of the property to add
 * @param propertySchema Schema for the new property
 */
export function addProperty(
  schema: JSONSchema,
  objectPointer: string,
  propertyName: string,
  propertySchema: JSONSchema,
): JSONSchema {
  const internalPointer = logicalToInternal(objectPointer);
  const copy = cloneDeep(schema);
  const objectNode = jsonpointer.get(copy, internalPointer);

  if (!objectNode || typeof objectNode !== 'object') {
    throw new Error(`Node at ${objectPointer} is not an object`);
  }

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
 * @param objectPointer Logical path to the parent object (e.g., "" for root, "/address" for nested)
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

  const internalPointer = logicalToInternal(objectPointer);
  const copy = cloneDeep(schema);
  const parentNode = jsonpointer.get(copy, internalPointer);

  if (!parentNode || typeof parentNode !== 'object') {
    throw new Error(`Node at ${objectPointer} is not an object`);
  }

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
 * @param fromObjectPointer Logical path to the source parent object
 * @param propertyName Name of the property to move
 * @param toObjectPointer Logical path to the target parent object
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
 * @param fromObjectPointer Logical path to the source parent object
 * @param propertyName Name of the property to clone
 * @param toObjectPointer Logical path to the target parent object
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
