import { useState, useCallback, useMemo, useRef } from 'react';
import { useSnackbar } from '@sema4ai/components';
import type { components } from '@sema4ai/agent-server-interface';
import {
  useGenerateExtractionSchemaMutation,
  useExtractDocumentMutation,
  useGetSchemaQuery,
} from '../../../../queries/documentIntelligence';
import type { ExtractSchemaResponse, ExtractResponse, ExtractionSchemaPayload } from '../../shared/types';
import { extractFieldPathsFromSchema, filterDataBySchema, filterCitationsBySchema } from '../utils/schemaUtils';

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

  // Fetch cached schema
  const { isLoading: isFetchingCachedSchema, refetch: refetchCachedSchema } = useGetSchemaQuery(
    { fileName: file.name, agentId, threadId },
    { enabled: false, retry: false },
  );

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

  const handleGenerateSchema = useCallback(
    async (generatePayload?: { instructions?: string; force: boolean }) => {
      try {
        const result = await generateSchema({
          agentId,
          threadId,
          formData: file,
          instructions: generatePayload?.instructions ?? '',
          force: generatePayload?.force ?? false,
        });

        setCurrentSchema(result.schema as ExtractionSchemaPayload);
        return result;
      } catch (err) {
        addSnackbar({ message: (err as Error).message, variant: 'danger' });
        return null;
      }
    },
    [file, threadId, agentId, generateSchema, addSnackbar],
  );

  // Fetch cached schema from the server if one already exists for this file
  const handleFetchCachedSchema = useCallback(async (): Promise<ExtractSchemaResponse | null> => {
    try {
      const result = await refetchCachedSchema();
      return (result.data as ExtractSchemaResponse) ?? null;
    } catch {
      return null; // 404 or error - fall back to generation
    }
  }, [refetchCachedSchema]);

  const handleExtract = useCallback(
    async (schemaResponse: ExtractSchemaResponse) => {
      try {
        const extractionSchema = (schemaResponse.schema.extract_schema ??
          schemaResponse.schema) as ExtractionSchemaPayload;

        const documentLayout: Partial<components['schemas']['DocumentLayoutPayload']> = {
          extraction_schema: extractionSchema,
        };

        const result = await extractDocument({
          threadId,
          fileName: file.name,
          documentLayout,
          generateCitations: true,
        });

        // Update current schema
        setCurrentSchema(extractionSchema);
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

        // Update current schema
        setCurrentSchema(updatedSchema);
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
    isFetchingCachedSchema,
    error,
    hasInitialized,

    // Actions
    handleGenerateSchema,
    handleFetchCachedSchema,
    handleExtract,
    handleReExtract,
    handleSchemaChange,
    initializeFromExisting,
    setHasChanges,
  };
};
