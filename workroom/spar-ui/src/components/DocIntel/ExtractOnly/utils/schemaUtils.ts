import type { ExtractionSchemaPayload } from '../../shared/types';

interface FieldDefinition {
  type?: string;
  properties?: Record<string, unknown>;
  items?: { type?: string; properties?: Record<string, unknown> };
}

/**
 * Extract all valid field paths from a schema definition.
 * Returns paths like: "inspector", "inspector.name", "inspected_components"
 */
export const extractFieldPathsFromSchema = (
  schema: ExtractionSchemaPayload | null,
  parentPath: string = '',
): Set<string> => {
  const paths = new Set<string>();

  if (!schema?.properties) {
    return paths;
  }

  Object.entries(schema.properties).forEach(([fieldName, fieldDef]) => {
    const currentPath = parentPath ? `${parentPath}.${fieldName}` : fieldName;
    paths.add(currentPath);

    const fieldDefTyped = fieldDef as FieldDefinition;

    if (fieldDefTyped.type === 'object' && fieldDefTyped.properties) {
      const nestedPaths = extractFieldPathsFromSchema(
        { properties: fieldDefTyped.properties } as ExtractionSchemaPayload,
        currentPath,
      );
      nestedPaths.forEach((path) => paths.add(path));
    }

    if (fieldDefTyped.type === 'array' && fieldDefTyped.items?.type === 'object' && fieldDefTyped.items.properties) {
      const arrayItemPaths = extractFieldPathsFromSchema(
        { properties: fieldDefTyped.items.properties } as ExtractionSchemaPayload,
        currentPath,
      );
      arrayItemPaths.forEach((path) => {
        const nestedField = path.replace(`${currentPath}.`, '');
        if (nestedField !== path) {
          paths.add(`${currentPath}.${nestedField}`);
        }
      });
    }
  });

  return paths;
};

/**
 * Filters data object to only include fields that exist in the valid paths set
 */
export const filterDataBySchema = (
  data: Record<string, unknown>,
  validPaths: Set<string>,
  currentPath: string = '',
): unknown => {
  if (!data || typeof data !== 'object') {
    return data;
  }

  if (Array.isArray(data)) {
    return data.map((item) => filterDataBySchema(item as Record<string, unknown>, validPaths, currentPath));
  }

  const filtered: Record<string, unknown> = {};
  Object.entries(data).forEach(([key, value]) => {
    const fieldPath = currentPath ? `${currentPath}.${key}` : key;

    if (validPaths.has(fieldPath)) {
      filtered[key] = filterDataBySchema(value as Record<string, unknown>, validPaths, fieldPath);
    }
  });

  return filtered;
};

/**
 * Filters citations to only include those that correspond to valid schema paths
 */
export const filterCitationsBySchema = (
  citations: Record<string, unknown>,
  validPaths: Set<string>,
): Record<string, unknown> => {
  const filterCitationsRecursive = (obj: unknown, currentPath: string = ''): unknown => {
    if (!obj || typeof obj !== 'object') {
      return obj;
    }

    if ('bbox' in obj && 'content' in obj) {
      return validPaths.has(currentPath) ? obj : null;
    }

    if (Array.isArray(obj)) {
      return obj.map((item) => filterCitationsRecursive(item, currentPath)).filter(Boolean);
    }

    const filtered: Record<string, unknown> = {};
    Object.entries(obj).forEach(([key, value]) => {
      const fieldPath = currentPath ? `${currentPath}.${key}` : key;
      const result = filterCitationsRecursive(value, fieldPath);
      if (result !== null && result !== undefined) {
        filtered[key] = result;
      }
    });

    return Object.keys(filtered).length > 0 ? filtered : null;
  };

  const result = filterCitationsRecursive(citations);
  return result as Record<string, unknown>;
};

/**
 * Finds all parent fields in a schema that have children (object or array types)
 */
export const findParentFields = (properties: Record<string, unknown>, parentPath: string = ''): Set<string> => {
  const expanded = new Set<string>();

  const traverse = (props: Record<string, unknown>, path: string = '') => {
    Object.entries(props).forEach(([fieldName, fieldValue]) => {
      const value = fieldValue as FieldDefinition;
      const fieldPath = path ? `${path}.${fieldName}` : fieldName;
      const hasChildren = Boolean(
        (value.type === 'object' && value.properties) ||
          (value.type === 'array' && value.items?.type === 'object' && value.items?.properties),
      );

      if (hasChildren) {
        expanded.add(fieldPath);

        if (value.type === 'object' && value.properties) {
          traverse(value.properties, fieldPath);
        }
        if (value.type === 'array' && value.items?.properties) {
          traverse(value.items.properties, fieldPath);
        }
      }
    });
  };

  traverse(properties, parentPath);
  return expanded;
};
