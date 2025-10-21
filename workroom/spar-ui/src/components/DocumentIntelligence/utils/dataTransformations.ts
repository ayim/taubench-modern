import { LayoutFieldRow, LayoutTableRow } from '../types';
import type {
  ParseDocumentResponsePayload,
  ExtractDocumentResponsePayload,
  ExtractionSchemaPayload,
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

// Remove citation from extracted data by field name
export const removeCitationFromExtractedData = (
  extractedData: ExtractDocumentResponsePayload,
  fieldName: string
): ExtractDocumentResponsePayload => {
  if (!extractedData?.citations) {
    return extractedData;
  }


  // Helper function to recursively remove citations by field name
  const removeCitationRecursively = (obj: unknown, currentPath: string = ''): unknown => {
    if (!obj || typeof obj !== 'object') return obj;

    // If this object is a citation (has bbox and content), check if it matches the field name
    if ('bbox' in obj && 'content' in obj) {
      const citationFieldName = formatFieldName(currentPath)
      // Try multiple matching strategies:
      // 1. Exact match
      const exactMatch = citationFieldName === fieldName;

      // 2. Case-insensitive match
      const caseInsensitiveMatch = citationFieldName.toLowerCase() === fieldName.toLowerCase();

      // 3. Match without array index (e.g., "inspection_summary_0" matches "inspection_summary")
      const withoutArrayIndex = citationFieldName.replace(/_\d+$/, '');
      const arrayIndexMatch = withoutArrayIndex === fieldName;

      // 4. Match the base path without array notation (e.g., "inspection_summary[0]" matches "inspection_summary")
      const basePath = currentPath.replace(/\[\d+\]$/, '');
      const basePathFormatted = formatFieldName(basePath);
      const basePathMatch = basePathFormatted === fieldName;

      if (exactMatch || caseInsensitiveMatch || arrayIndexMatch || basePathMatch) {
        return null; // Mark for removal
      }
      return obj;
    }

    // If it's an array, process each item and filter out nulls
    if (Array.isArray(obj)) {
      return obj
        .map((item, index) => removeCitationRecursively(item, `${currentPath}[${index}]`))
        .filter(item => item !== null);
    }

    // If it's an object, process each property
    const result: Record<string, unknown> = {};
    Object.entries(obj).forEach(([key, value]) => {
      const newPath = currentPath ? `${currentPath}.${key}` : key;
      const processedValue = removeCitationRecursively(value, newPath);
      if (processedValue !== null) {
        result[key] = processedValue;
      }
    });

    return result;
  };

  const updatedCitations = removeCitationRecursively(extractedData.citations);

  return {
    ...extractedData,
    citations: updatedCitations as typeof extractedData.citations,
  };
};

// Convert parse result to bounding boxes for display
export const convertParseResultToBoundingBoxes = (parseResult: ParseDocumentResponsePayload): Array<{
  fieldId: string;
  coords: { left: number; top: number; width: number; height: number };
  fieldName: string;
  fieldValue: string;
  numericId: number;
  type?: string;
  confidence?: string;
}> => {
  const boundingBoxes: Array<{
    fieldId: string;
    coords: { left: number; top: number; width: number; height: number };
    fieldName: string;
    fieldValue: string;
    numericId: number;
    type?: string;
    confidence?: string;
  }> = [];

  if (!parseResult?.chunks || !Array.isArray(parseResult.chunks)) {
    return boundingBoxes;
  }
  let numericIdCounter = 1;

  parseResult.chunks.forEach((chunk, chunkIndex) => {
    // Use chunk content as the field value
    const fieldValue = chunk.content || '';


    // Skip empty chunks
    if (!fieldValue.trim()) {
      return;
    }

    // Check if chunk itself has a bounding box (for chunks without blocks)
    if (chunk.bbox && typeof chunk.bbox === 'object') {
      const chunkBbox = chunk.bbox as { left?: number; top?: number; width?: number; height?: number; page?: number };
      const coords = {
        left: chunkBbox.left || 0,
        top: chunkBbox.top || 0,
        width: chunkBbox.width || 0,
        height: chunkBbox.height || 0,
      };

      // Skip boxes with zero dimensions
      if (coords.width > 0 && coords.height > 0) {
        boundingBoxes.push({
          fieldId: `parse-chunk-${chunkIndex}`,
          coords,
          fieldName: formatFieldName(fieldValue.substring(0, 50)),
          fieldValue: String(fieldValue),
          numericId: numericIdCounter,
          type: (chunk as { type?: string }).type || 'Text', // Extract type from chunk, default to 'Text'
          confidence: (chunk as { confidence?: string }).confidence || 'high', // Extract confidence from chunk, default to 'high'
        });
      }
    }

    // Process each block in the chunk
    if (chunk.blocks && Array.isArray(chunk.blocks)) {
      chunk.blocks.forEach((block, blockIndex) => {

        // Check if block has bounding box data
        if (block.bbox && typeof block.bbox === 'object') {
          const bbox = block.bbox as { left?: number; top?: number; width?: number; height?: number; page?: number };

          // Extract field name from block content or use chunk content
          const fieldName = block.content || chunk.content || `parse_field_${chunkIndex}_${blockIndex}`;

          // Skip empty field names
          if (!fieldName.trim()) {
            return;
          }

          // Convert bbox coordinates to screen coordinates
          // Parse bbox coordinates are typically normalized (0-1) or in PDF points
          const coords = {
            left: bbox.left || 0,
            top: bbox.top || 0,
            width: bbox.width || 0,
            height: bbox.height || 0,
          };

          // Skip boxes with zero dimensions
          if (coords.width <= 0 || coords.height <= 0) {
            return;
          }

          boundingBoxes.push({
            fieldId: `parse-${chunkIndex}-${blockIndex}`,
            coords,
            fieldName: formatFieldName(fieldName),
            fieldValue: String(fieldValue),
            numericId: numericIdCounter,
            type: (block as { type?: string }).type || 'Text', // Extract type from block, default to 'Text'
            confidence: (block as { confidence?: string }).confidence || 'high', // Extract confidence from block, default to 'high'
          });

          numericIdCounter += 1;
        }
      });
    } else {
      // If no blocks, try to use chunk-level bounding box if available
      // This is a fallback for chunks that might have bbox at the chunk level
      const fieldName = chunk.content || `parse_chunk_${chunkIndex}`;

      boundingBoxes.push({
        fieldId: `parse-chunk-${chunkIndex}`,
        coords: { left: 0, top: 0, width: 100, height: 20 }, // Default fallback coordinates
        fieldName: formatFieldName(fieldName),
        fieldValue: String(fieldValue),
        numericId: numericIdCounter,
        type: (chunk as { type?: string }).type || 'Text', // Extract type from chunk, default to 'Text'
        confidence: (chunk as { confidence?: string }).confidence || 'high', // Extract confidence from chunk, default to 'high'
      });

      numericIdCounter += 1;
    }
  });

  return boundingBoxes;
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

// Convert UI state to DocumentLayoutPayload for retry functionality
export const convertUIStateToDocumentLayoutPayload = (
  layoutFields: LayoutFieldRow[],
  layoutTables: LayoutTableRow[],
  documentLayout?: { prompt?: string | null } | null,
  originalGeneratedSchema?: ExtractionSchemaPayload | null
): Record<string, unknown> => {
  // Start with the original generated schema if available, otherwise create a new one
  let baseSchema: Record<string, unknown>;

  if (originalGeneratedSchema) {
    // Use the original schema as base, preserving its structure
    baseSchema = { ...originalGeneratedSchema };
  } else {
    // Fallback to creating a basic schema
    baseSchema = {
      type: 'object',
      properties: {},
      required: [],
    };
  }

  // Helper function to get original schema property by path
  const getOriginalSchemaProperty = (path: string): Record<string, unknown> | null => {
    if (!originalGeneratedSchema?.properties) return null;

    const pathParts = path.split('.');
    const current: Record<string, unknown> = originalGeneratedSchema.properties;

    const result = pathParts.reduce<Record<string, unknown> | null>((acc, part) => {
      if (acc && acc[part] && typeof acc[part] === 'object') {
        return acc[part] as Record<string, unknown>;
      }
      return null;
    }, current);

    return result;
  };

  // Create extraction schema from fields and tables
  const properties: Record<string, Record<string, unknown>> = {};
  const required: string[] = [];

  // Add fields to schema
  layoutFields.forEach((field) => {
    if (field.name && field.name.trim()) {
      const fieldName = formatFieldName(field.name);

      // Get original schema property to preserve description and layout_description
      const originalProperty = getOriginalSchemaProperty(fieldName);

      properties[fieldName] = {
        type: field.type || 'string',
        description: field.description || originalProperty?.description || '',
        layout_description: field.layout_description || originalProperty?.layout_description || '',
      };

      if (field.required) {
        required.push(fieldName);
      }
    }
  });

  // Add tables to schema
  layoutTables.forEach((table) => {
    if (table.name && table.name.trim()) {
      const tableName = formatFieldName(table.name);
      const tableProperties: Record<string, Record<string, unknown>> = {};
      const tableRequired: string[] = [];

      // Get original table schema property
      const originalTableProperty = getOriginalSchemaProperty(tableName);

      // Add table columns
      if (table.columnsMeta) {
        Object.entries(table.columnsMeta).forEach(([columnName, meta]) => {
          const columnFieldName = formatFieldName(columnName);

          // Get original column property from table items
          let originalColumnProperty: Record<string, unknown> | null = null;
          if (originalTableProperty?.items && typeof originalTableProperty.items === 'object') {
            const items = originalTableProperty.items as Record<string, unknown>;
            if (items.properties && typeof items.properties === 'object') {
              const itemsProps = items.properties as Record<string, unknown>;
              originalColumnProperty = itemsProps[columnFieldName] as Record<string, unknown> || null;
            }
          }

          tableProperties[columnFieldName] = {
            type: meta.type || 'string',
            description: meta.description || originalColumnProperty?.description || '',
            layout_description: meta.layout_description || originalColumnProperty?.layout_description || '',
          };

          if (meta.required) {
            tableRequired.push(columnFieldName);
          }
        });
      }

      properties[tableName] = {
        type: 'array',
        items: {
          type: 'object',
          properties: tableProperties,
          required: tableRequired,
        },
        description: table.description || originalTableProperty?.description || '',
        layout_description: table.layout_description || originalTableProperty?.layout_description || '',
      };
    }
  });

  // Update the base schema with our properties and requirements
  const updatedSchema = {
    ...baseSchema,
    properties,
    required,
  };

  return {
    extraction_schema: updatedSchema,
    prompt: documentLayout?.prompt || null,
    summary: null,
    extraction_config: null,
  };
};
