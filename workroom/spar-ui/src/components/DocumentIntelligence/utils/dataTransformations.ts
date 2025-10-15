import { LayoutFieldRow, LayoutTableRow } from '../types';
import type {
  ParseDocumentResponsePayload,
  ExtractDocumentResponsePayload,
} from '../store/useDocumentIntelligenceStore';

// Union type for both parse and extract responses
type DocumentResponsePayload = ParseDocumentResponsePayload | ExtractDocumentResponsePayload;

// Type definitions for extraction schema
interface SchemaProperty {
  type: string;
  description?: string;
  layout_description?: string;
  properties?: Record<string, SchemaProperty>;
  required?: string[];
  items?: SchemaProperty;
}

interface ExtractionSchema {
  $schema: string;
  title: string;
  type: string;
  properties: Record<string, SchemaProperty>;
  required: string[];
}

// Utility function to generate unique IDs
export const generateUniqueId = (prefix: string): string => {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

// Utility function to format field names
export const formatFieldName = (name: string): string => {
  return name
    .replace(/[^a-zA-Z0-9._-]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '');
};

export const formatDataModelName = (dataModelName: string): string => {
  return dataModelName
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};

export const toSnakeCase = (s: string): string => {
  return s
    .replace(/([A-Z])/g, '_$1')
    .replace(/^_/, '')
    .replace(/(\d+)/g, '_$1_')
    .replace(/[^a-zA-Z0-9_]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
    .toLowerCase();
};

export const formatSqlQuery = (sqlQuery: string): string => {
  if (!sqlQuery) return '';

  return sqlQuery
    .replace(/\s+/g, ' ')
    .replace(/\bSELECT\b/gi, 'SELECT\n  ')
    .replace(/\bFROM\b/gi, '\nFROM\n  ')
    .replace(/\bWHERE\b/gi, '\nWHERE\n  ')
    .replace(/\bGROUP BY\b/gi, '\nGROUP BY\n  ')
    .replace(/\bORDER BY\b/gi, '\nORDER BY\n  ')
    .replace(/\bHAVING\b/gi, '\nHAVING\n  ')
    .replace(/\bAND\b/gi, '\n  AND ')
    .replace(/\bOR\b/gi, '\n  OR ')
    .replace(/,(?!\s*\))/g, ',\n  ')
    .trim();
};

// Convert parse result to fields format
export const convertParseResultToFields = (parseResult: DocumentResponsePayload): LayoutFieldRow[] => {
  const extractedFields: LayoutFieldRow[] = [];

  // Handle parse response (has chunks)
  if ('chunks' in parseResult && parseResult.chunks && Array.isArray(parseResult.chunks)) {
    // Process chunks where each chunk has blocks and content
    const { chunks } = parseResult;
    let numericIdCounter = 1;

    chunks.forEach((chunk, index) => {
      // Extract field name from the first block's content, or use content directly
      const fieldName = chunk.blocks?.[0]?.content || chunk.content || `field_${index}`;
      const fieldValue = chunk.content || '';

      // Skip empty or whitespace-only fields
      if (!fieldName.trim() || !fieldValue.trim()) {
        return;
      }

      extractedFields.push({
        id: generateUniqueId('field'),
        type: 'string',
        required: true,
        name: formatFieldName(fieldName),
        value: String(fieldValue),
        citationId: numericIdCounter,
      });
      numericIdCounter += 1;
    });

    return extractedFields;
  }

  // Handle extract response (has result)
  if ('result' in parseResult && parseResult.result && typeof parseResult.result === 'object') {
    // Helper function to recursively flatten nested objects
    const flattenObject = (obj: Record<string, unknown>, prefix: string = ''): Record<string, string | number> => {
      const flattened: Record<string, string | number> = {};

      Object.entries(obj).forEach(([key, value]) => {
        const newKey = prefix ? formatFieldName(`${prefix}.${key}`) : formatFieldName(key);

        // Skip special fields that are metadata
        if (['confidence', 'processing_time', 'errors'].includes(key)) {
          return;
        }

        if (value === null || value === undefined) {
          // Handle null/undefined values
          flattened[newKey] = '';
        } else if (Array.isArray(value)) {
        // Skip arrays - they are handled by tables
        } else if (typeof value === 'object' && value !== null) {
          // Recursively flatten nested objects
          const nestedFlattened = flattenObject(value as Record<string, unknown>, newKey);
          Object.assign(flattened, nestedFlattened);
        } else if (typeof value === 'string' || typeof value === 'number') {
          // Handle string and number values
          flattened[newKey] = value;
        } else if (typeof value === 'boolean') {
          // Convert boolean values to strings
          flattened[newKey] = String(value);
        }
      });

      return flattened;
    };

    // Flatten the result data
    const flattenedData = flattenObject(parseResult.result as Record<string, unknown>);
    let numericIdCounter = 1; // Start from 1 for human-readable IDs

    Object.entries(flattenedData).forEach(([key, value]) => {
      // Remove 'result.' prefix from field names
      const cleanKey = key.startsWith('result.') ? key.substring(7) : key;

      extractedFields.push({
        id: generateUniqueId('field'),
        type: 'string',
        required: true,
        name: cleanKey,
        value: String(value),
        // Add numeric ID for citation matching
        citationId: numericIdCounter,
      });
      numericIdCounter += 1;
    });

    return extractedFields;
  }

  return extractedFields;
};

// Convert parse result to tables format
export const convertParseResultToTables = (parseResult: DocumentResponsePayload): LayoutTableRow[] => {
  const extractedTables: LayoutTableRow[] = [];
  let tableCounter = 0;

  // Helper function to recursively search for arrays
  const searchForArrays = (obj: Record<string, unknown>, prefix: string = '') => {
    if (!obj || typeof obj !== 'object') {
      return;
    }

    Object.entries(obj).forEach(([key, value]) => {
      const currentPath = prefix ? `${prefix}.${key}` : key;

      if (Array.isArray(value) && value.length > 0) {
        // Check if array contains objects (potential table data)
        if (value.some((item) => item && typeof item === 'object' && !Array.isArray(item))) {
          // Get all possible columns from all items in the array
          const allKeys = new Set<string>();
          value.forEach((item) => {
            if (item && typeof item === 'object' && !Array.isArray(item)) {
              Object.keys(item).forEach((k) => allKeys.add(k));
            }
          });

          const columns = Array.from(allKeys);

          const table: LayoutTableRow = {
            id: `table-${tableCounter}`,
            required: true,
            description: '',
            name: formatFieldName(currentPath),
            columns,
            columnsMeta: columns.reduce(
              (acc, col) => {
                acc[col] = { type: 'string', required: true, description: '' };
                return acc;
              },
              {} as Record<string, { type: string; required: boolean; description: string }>,
            ),
            data: value
              .filter((item) => item && typeof item === 'object' && !Array.isArray(item))
              .map((item) => {
                const row: Record<string, string> = {};
                columns.forEach((col) => {
                  row[col] = item[col] !== undefined && item[col] !== null ? String(item[col]) : '';
                });
                return row;
              }),
          };
          extractedTables.push(table);
          tableCounter += 1;
        }

        // Continue searching recursively in array items
        value.forEach((item) => {
          if (item && typeof item === 'object' && !Array.isArray(item)) {
            searchForArrays(item, currentPath);
          }
        });
      } else if (value && typeof value === 'object' && !Array.isArray(value)) {
        // Recursively search in nested objects
        searchForArrays(value as Record<string, unknown>, currentPath);
      }
    });
  };

  // Process the chunks directly from the API response (parse response)
  if ('chunks' in parseResult && parseResult.chunks && Array.isArray(parseResult.chunks)) {
    parseResult.chunks.forEach((chunk) => {
      if (chunk.content) {
        try {
          // Try to parse the content as JSON to find structured data
          const parsedContent = JSON.parse(chunk.content);
          if (parsedContent && typeof parsedContent === 'object') {
            searchForArrays(parsedContent);
          }
        } catch {
          // If parsing fails, continue with the next chunk
        }
      }
    });
  }

  // Process the result from extract response
  if ('result' in parseResult && parseResult.result && typeof parseResult.result === 'object') {
    searchForArrays(parseResult.result as Record<string, unknown>);
  }

  return extractedTables;
};

// Convert fields to extraction schema format
export const convertFieldsToExtractionSchema = (fields: LayoutFieldRow[]): Record<string, SchemaProperty> => {
  // Helper function to build nested properties recursively
  const buildNestedProperties = (
    fieldGroup: LayoutFieldRow[],
    pathPrefix: string = '',
  ): {
    properties: Record<string, SchemaProperty>;
    required: string[];
  } => {
    const properties: Record<string, SchemaProperty> = {};
    const required: string[] = [];

    // Group fields by their immediate next level
    const groupedFields: Record<string, LayoutFieldRow[]> = {};
    const directFields: LayoutFieldRow[] = [];

    fieldGroup.forEach((field) => {
      const relativePath = pathPrefix ? field.name.substring(pathPrefix.length + 1) : field.name;
      const pathParts = relativePath.split('.');

      if (pathParts.length === 1) {
        // This is a direct field at this level
        directFields.push(field);
      } else {
        // This field belongs to a nested object
        const nextLevel = pathParts[0];
        if (!groupedFields[nextLevel]) {
          groupedFields[nextLevel] = [];
        }
        groupedFields[nextLevel].push(field);
      }
    });

    // Process direct fields
    directFields.forEach((field) => {
      const fieldName = pathPrefix ? field.name.substring(pathPrefix.length + 1) : field.name;

      properties[fieldName] = {
        type: field.type || 'string',
        description: field.description || '',
        // Fallback to description if no specific layout instructions provided
        layout_description: field.layout_description || field.description || '',
        required: field.required ? [fieldName] : undefined,
      };
    });

    // Process nested objects
    Object.entries(groupedFields).forEach(([key, nestedFields]) => {
      const nestedPath = pathPrefix ? `${pathPrefix}.${key}` : key;
      const nested = buildNestedProperties(nestedFields, nestedPath);

      properties[key] = {
        type: 'object',
        properties: nested.properties,
        required: nested.required,
      };

      // Add to required if any of the nested fields are enabled
      const hasEnabledFields = nestedFields.find((field) => field.required);
      if (hasEnabledFields) {
        required.push(key);
      }
    });

    return { properties, required };
  };

  // Build the root level properties from fields
  const { properties: fieldsProperties } = buildNestedProperties(fields);
  return fieldsProperties;
};

// Convert tables to extraction schema format
export const convertTablesToExtractionSchema = (tables: LayoutTableRow[]): Record<string, SchemaProperty> => {
  const schema: Record<string, SchemaProperty> = {};

  tables.forEach((table) => {
    const hierarchy = table.name.split('.');
    const lastLevel = hierarchy[hierarchy.length - 1];

    if (hierarchy.length > 1) {
      const parentKey = hierarchy[0];

      // Create or get existing parent schema
      if (!schema[parentKey]) {
        schema[parentKey] = {
          type: 'object',
          properties: {},
          required: [],
        };
      }

      let currentSchema = schema[parentKey];

      // Navigate/create the hierarchy, stopping before the last level
      for (let i = 1; i < hierarchy.length - 1; i += 1) {
        const level = hierarchy[i];

        if (!currentSchema.properties) currentSchema.properties = {};

        if (!currentSchema.properties[level]) {
          currentSchema.properties[level] = {
            type: 'object',
            properties: {},
            required: [],
          };
        }

        // Add to required array if not already present
        if (!currentSchema.required) currentSchema.required = [];
        if (!currentSchema.required.includes(level)) {
          currentSchema.required.push(level);
        }
        currentSchema = currentSchema.properties[level];
      }

      // Add the final array property
      if (!currentSchema.properties) currentSchema.properties = {};
      currentSchema.properties[lastLevel] = {
        type: 'array',
        description: `Array of ${table.name} table rows`,
        // Fallback to description if no specific layout instructions provided
        layout_description: table.layout_description || table.description || '',
        items: {
          type: 'object',
          properties: table.columns.reduce(
            (acc, column) => {
              acc[column] = {
                type: table.columnsMeta[column]?.type || 'string',
                description: table.columnsMeta[column]?.description || column,
                // Fallback to description if no specific layout instructions provided
                layout_description:
                  table.columnsMeta[column]?.layout_description ||
                  table.columnsMeta[column]?.description ||
                  column,
              };
              return acc;
            },
            {} as Record<string, SchemaProperty>,
          ),
          required: table.columns.filter((column) => table.columnsMeta[column]?.required !== false),
        },
      };

      // Add the final level to its parent's required array
      if (!currentSchema.required) currentSchema.required = [];
      if (!currentSchema.required.includes(lastLevel)) {
        currentSchema.required.push(lastLevel);
      }
    } else {
      schema[lastLevel] = {
        type: 'array',
        description: `Array of ${table.name} table rows`,
        // Fallback to description if no specific layout instructions provided
        layout_description: table.layout_description || table.description || '',
        items: {
          type: 'object',
          properties: table.columns.reduce(
            (acc, column) => {
              acc[column] = {
                type: table.columnsMeta[column]?.type || 'string',
                description: table.columnsMeta[column]?.description || column,
                // Fallback to description if no specific layout instructions provided
                layout_description:
                  table.columnsMeta[column]?.layout_description ||
                  table.columnsMeta[column]?.description ||
                  column,
              };
              return acc;
            },
            {} as Record<string, SchemaProperty>,
          ),
          required: table.columns.filter((column) => table.columnsMeta[column]?.required !== false),
        },
      };
    }
  });

  return schema;
};

// Merge extracted schema properties
export const mergeExtractedSchemaProperties = (extractedSchemaProperties: Record<string, SchemaProperty>[]): Record<string, SchemaProperty> => {
  const mergedSchema: Record<string, SchemaProperty> = {};

  // Helper function to deeply merge two schema properties
  const deepMergeSchemaProperty = (target: SchemaProperty, source: SchemaProperty): SchemaProperty => {
    const result: SchemaProperty = { ...target };

    // Merge properties if both are objects
    if (target.properties && source.properties) {
      result.properties = { ...target.properties, ...source.properties };
    } else if (source.properties) {
      result.properties = source.properties;
    }

    // Merge required arrays
    if (target.required && source.required) {
      result.required = Array.from(new Set([...target.required, ...source.required]));
    } else if (source.required) {
      result.required = source.required;
    }

    // Use source values for other properties (type, description, layout_description, etc.)
    return {
      ...result,
      type: source.type || target.type,
      description: source.description || target.description,
      // Fallback to description if no specific layout instructions provided
      layout_description:
        source.layout_description || source.description || target.layout_description || target.description || '',
      items: source.items || target.items,
    };
  };

  extractedSchemaProperties.forEach((schema) => {
    Object.entries(schema).forEach(([key, property]) => {
      if (mergedSchema[key]) {
        // Deep merge if key already exists
        mergedSchema[key] = deepMergeSchemaProperty(mergedSchema[key], property);
      } else {
        // Add new key
        mergedSchema[key] = property;
      }
    });
  });

  return mergedSchema;
};

// Convert layout to extraction schema
export const convertLayoutToExtractionSchema = (fields: LayoutFieldRow[], tables: LayoutTableRow[]): ExtractionSchema => {
  const schemaProperties: Record<string, SchemaProperty>[] = [
    convertFieldsToExtractionSchema(fields),
    convertTablesToExtractionSchema(tables),
  ];
  const mergedSchema = mergeExtractedSchemaProperties(schemaProperties);
  const requiredFields = Object.entries(mergedSchema || {})
    .filter(([, property]) => !!property.required)
    .map(([name]) => name);
  return {
    $schema: 'http://json-schema.org/draft-07/schema#',
    title: 'Document Extraction Schema',
    type: 'object',
    properties: mergedSchema,
    required: requiredFields,
  };
};

// Filter fields by selected fields
export const filterFieldsBySelectedFields = ({
  fields,
  selectedFields,
}: {
  fields: LayoutFieldRow[];
  selectedFields: number[];
}): LayoutFieldRow[] => {
  return selectedFields?.length > 0 ? fields.filter((_, index) => selectedFields.includes(index)) : fields;
};

// Filter tables by selected table columns
export const filterTablesBySelectedTableColumns = ({
  tables,
  selectedTableColumns,
}: {
  tables: LayoutTableRow[];
  selectedTableColumns: Record<string, number[]>;
}): LayoutTableRow[] => {
  return Object.keys(selectedTableColumns).some((tableName) => selectedTableColumns[tableName].length > 0)
    ? tables
        .filter((table) => selectedTableColumns[table.name] && selectedTableColumns[table.name].length > 0)
        .map((table) => {
          const selectedColumnIndices = selectedTableColumns[table.name];
          const filteredColumns = table.columns.filter((_, index) => selectedColumnIndices.includes(index));
          const filteredColumnsMeta = Object.fromEntries(
            Object.entries(table.columnsMeta).filter(([columnName]) => filteredColumns.includes(columnName)),
          );
          const filteredData = table.data.map((row) =>
            Object.fromEntries(
              Object.entries(row).filter(([columnName]) => filteredColumns.includes(columnName)),
            ),
          );

          return {
            ...table,
            columns: filteredColumns,
            columnsMeta: filteredColumnsMeta,
            data: filteredData,
          };
        })
    : tables;
};
