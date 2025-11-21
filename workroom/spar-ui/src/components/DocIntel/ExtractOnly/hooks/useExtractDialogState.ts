import { useState, useCallback, useMemo, useRef } from 'react';
import { useSnackbar } from '@sema4ai/components';
import type { components } from '@sema4ai/agent-server-interface';
import {
  useGenerateExtractionSchemaMutation,
  useExtractDocumentMutation,
} from '../../../../queries/documentIntelligence';
import type { ExtractSchemaResponse, ExtractResponse, ExtractionSchemaPayload } from '../../shared/types';
import { extractFieldPathsFromSchema, filterDataBySchema, filterCitationsBySchema } from '../utils/schemaUtils';

/**
 * Remove isNewField flags from schema properties after successful extraction
 */
const clearNewFieldFlags = (schema: ExtractionSchemaPayload): ExtractionSchemaPayload => {
  const cleanProperties = (properties: Record<string, unknown>): Record<string, unknown> => {
    const cleaned: Record<string, unknown> = {};

    Object.entries(properties).forEach(([key, value]) => {
      const fieldValue = value as Record<string, unknown>;
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { isNewField, ...rest } = fieldValue;

      cleaned[key] = rest;

      // Recursively clean nested properties
      if (rest.type === 'object' && rest.properties) {
        cleaned[key] = {
          ...rest,
          properties: cleanProperties(rest.properties as Record<string, unknown>),
        };
      } else if (rest.type === 'array' && rest.items && typeof rest.items === 'object') {
        const items = rest.items as Record<string, unknown>;
        if (items.type === 'object' && items.properties) {
          cleaned[key] = {
            ...rest,
            items: {
              ...items,
              properties: cleanProperties(items.properties as Record<string, unknown>),
            },
          };
        }
      }
    });

    return cleaned;
  };

  return {
    ...schema,
    properties: cleanProperties(schema.properties),
  };
};

interface UseExtractDialogStateProps {
  agentId: string;
  threadId: string;
  file: File;
  schema?: ExtractSchemaResponse;
  extractResult?: ExtractResponse;
}

export const useExtractDialogState = ({
  agentId,
  threadId,
  file,
  schema,
  extractResult: initialExtractResult,
}: UseExtractDialogStateProps) => {
  const { addSnackbar } = useSnackbar();
  const hasInitialized = useRef(false);

  // Extract result from the backend
  const [extractResult, setExtractResult] = useState<ExtractResponse | null>(initialExtractResult ?? null);

  // Current working schema - the jsonschema that user can modify
  // Initialized from backend response, then becomes the editable version
  const [currentSchema, setCurrentSchema] = useState<ExtractionSchemaPayload | null>(
    (schema?.schema as ExtractionSchemaPayload) ?? null,
  );

  // Boolean to track if user has modified the schema since last extraction
  const [hasChanges, setHasChanges] = useState(false);

  // Counter incremented on each extraction to force PDF viewer re-render with new annotations
  const [extractRevision, setExtractRevision] = useState(0);

  const {
    mutateAsync: generateSchema,
    isPending: isGeneratingSchema,
    error: schemaError,
  } = useGenerateExtractionSchemaMutation({});

  const { mutateAsync: extractDocument, isPending: isExtracting, error: extractError } = useExtractDocumentMutation({});

  const extractedDataWithCitations = useMemo(() => {
    if (!extractResult) return null;

    if (currentSchema && hasChanges) {
      const validPaths = extractFieldPathsFromSchema(currentSchema);
      const filteredResult = filterDataBySchema(extractResult.result, validPaths);
      const filteredCitations = filterCitationsBySchema(extractResult.citations as Record<string, unknown>, validPaths);

      return {
        ...(filteredResult as Record<string, unknown>),
        citations: filteredCitations,
      };
    }

    return {
      ...extractResult.result,
      citations: extractResult.citations,
    };
  }, [extractResult, currentSchema, hasChanges]);

  const handleGenerateSchema = useCallback(async () => {
    try {
      const result = await generateSchema({
        agentId,
        threadId,
        formData: file,
      });

      setCurrentSchema(result.schema as ExtractionSchemaPayload);
      return result;
    } catch (err) {
      addSnackbar({ message: (err as Error).message, variant: 'danger' });
      throw err;
    }
  }, [file, threadId, agentId, generateSchema, addSnackbar]);

  const handleExtract = useCallback(
    async (schemaResponse: ExtractSchemaResponse) => {
      try {
        const extractionSchema = schemaResponse.schema as ExtractionSchemaPayload;

        const documentLayout: Partial<components['schemas']['DocumentLayoutPayload']> = {
          extraction_schema: extractionSchema,
        };

        const result = await extractDocument({
          threadId,
          fileName: file.name,
          documentLayout,
          generateCitations: true,
        });

        // Clear isNewField flags after successful extraction
        const cleanedSchema = clearNewFieldFlags(extractionSchema);
        setCurrentSchema(cleanedSchema);
        setExtractResult(result);
        setExtractRevision((prev) => prev + 1);
        setHasChanges(false);
      } catch (err) {
        addSnackbar({ message: (err as Error).message, variant: 'danger' });
      }
    },
    [threadId, file.name, extractDocument, addSnackbar],
  );

  const handleReExtract = useCallback(
    async (updatedSchema: ExtractionSchemaPayload, prompt: string) => {
      try {
        const documentLayout: Partial<components['schemas']['DocumentLayoutPayload']> = {
          extraction_schema: updatedSchema,
          ...(prompt && { prompt }),
        };

        const result = await extractDocument({
          threadId,
          fileName: file.name,
          documentLayout,
          generateCitations: true,
        });

        // Clear isNewField flags after successful extraction
        const cleanedSchema = clearNewFieldFlags(updatedSchema);
        setCurrentSchema(cleanedSchema);
        setExtractResult(result);
        setExtractRevision((prev) => prev + 1);
        setHasChanges(false);
      } catch (err) {
        addSnackbar({ message: (err as Error).message, variant: 'danger' });
        throw err;
      }
    },
    [threadId, file.name, extractDocument, addSnackbar],
  );

  const handleSchemaChange = useCallback((updatedSchema: ExtractionSchemaPayload | null) => {
    setCurrentSchema(updatedSchema);
  }, []);

  // Initialize from existing schema and extract result (e.g., from thread state)
  const initializeFromExisting = useCallback(
    (schemaResponse: ExtractSchemaResponse, extractResponse: ExtractResponse) => {
      setCurrentSchema(schemaResponse.schema as ExtractionSchemaPayload);
      setExtractResult(extractResponse);
    },
    [],
  );

  const error = schemaError?.message || extractError?.message || null;

  return {
    // State
    extractResult,
    currentSchema,
    hasChanges,
    extractRevision,
    extractedDataWithCitations,
    isGeneratingSchema,
    isExtracting,
    error,
    hasInitialized,

    // Actions
    handleGenerateSchema,
    handleExtract,
    handleReExtract,
    handleSchemaChange,
    initializeFromExisting,
    setHasChanges,
  };
};
