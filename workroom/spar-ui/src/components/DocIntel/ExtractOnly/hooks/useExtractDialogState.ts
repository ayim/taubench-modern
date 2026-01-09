import { useState, useCallback, useMemo, useRef } from 'react';
import { useSnackbar } from '@sema4ai/components';
import {
  useGenerateExtractionSchemaMutation,
  useGetSchemaQuery,
  useSimpleExtractMutation,
} from '../../../../queries/documentIntelligence';
import type { SimpleExtractResponse, ExtractSchemaResponse, ExtractionSchemaPayload } from '../../shared/types';
import { extractFieldPathsFromSchema, filterDataBySchema, filterCitationsBySchema } from '../utils/schemaUtils';
import {
  type ConfigurationSchema,
  toJSONDocumentSchema,
  RenderedField,
  toRenderedDocumentSchema,
} from '../../shared/utils/schema-lib';

/**
 * Extracts just the user's original instructions from the full formatted prompt.
 * The backend stores the full prompt which includes "# Instructions" + user text + "# Schema reference" + schema.
 * This function parses out just the user's original instructions.
 *
 * TODO https://linear.app/sema4ai/issue/DIN-XXX: Backend should return raw user instructions separately
 */
const parseUserInstructions = (userPrompt: string | null | undefined): string | null => {
  if (!userPrompt) return null;

  // Look for content between "# Instructions" and "# Schema reference"
  const instructionsRegex = /# Instructions\s*([\s\S]*?)(?=# Schema reference|$)/i;
  const instructionsMatch = instructionsRegex.exec(userPrompt);
  if (!instructionsMatch) return null;

  const instructions = instructionsMatch[1].trim();
  return instructions || null;
};

interface UseExtractDialogStateProps {
  agentId: string;
  threadId: string;
  file: File;
  schema?: ExtractSchemaResponse;
  extractResult?: SimpleExtractResponse;
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

  const [extractResult, setExtractResult] = useState<SimpleExtractResponse | null>(initialExtractResult ?? null);

  // Current working schema - the jsonschema that user can modify
  // Initialized from backend response, then becomes the editable version
  const [currentSchema, setCurrentSchema] = useState<ExtractionSchemaPayload | null>(
    (schema?.schema as ExtractionSchemaPayload) ?? null,
  );
  const [configuratorSchema, setConfiguratorSchema] = useState<ConfigurationSchema>({
    type: 'object',
    children: [],
  });

  const setCurrentConfiguratorSchema = useCallback((schemaProp: ExtractionSchemaPayload | null) => {
    setCurrentSchema(schemaProp);
    const result = toRenderedDocumentSchema(schemaProp);
    if (result.success) {
      setConfiguratorSchema({ type: 'object', children: result.data.fields } as ConfigurationSchema);
    } else {
      setConfiguratorSchema({ type: 'object', children: [] });
    }
  }, []);

  // Boolean to track if user has modified the schema since last extraction
  const [hasChanges, setHasChanges] = useState(false);
  const [extractRevision, setExtractRevision] = useState(0);

  // User prompt from schema generation - used to pre-populate business instructions
  const [userPrompt, setUserPrompt] = useState<string | null>(parseUserInstructions(schema?.user_prompt));

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

  const { mutateAsync: simpleExtract, isPending: isExtracting, error: extractError } = useSimpleExtractMutation({});

  const extractedDataWithCitations = useMemo(() => {
    if (!extractResult) return null;

    if (currentSchema && hasChanges) {
      const validPaths = extractFieldPathsFromSchema(currentSchema);
      const filteredResult = filterDataBySchema(extractResult.results, validPaths);
      const filteredCitations = filterCitationsBySchema(extractResult.citations as Record<string, unknown>, validPaths);

      return {
        ...(filteredResult as Record<string, unknown>),
        citations: filteredCitations,
      };
    }

    return {
      ...extractResult.results,
      citations: extractResult.citations,
    };
  }, [extractResult, currentSchema, hasChanges]);

  const handleGenerateSchema = useCallback(
    async (generatePayload?: { instructions?: string; force: boolean }) => {
      try {
        const result = await generateSchema({
          agentId,
          threadId,
          formData: file.name,
          instructions: generatePayload?.instructions ?? '',
          force: generatePayload?.force ?? false,
        });

        setCurrentSchema(result.schema as ExtractionSchemaPayload);
        setUserPrompt(parseUserInstructions(result.user_prompt));
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
      if (result.data) {
        setUserPrompt(parseUserInstructions(result.data.user_prompt));
      }
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

        const result = await simpleExtract({
          agentId,
          threadId,
          fileRef: file.name,
          extractionSchema,
        });

        // Update current schema
        setCurrentConfiguratorSchema(extractionSchema);
        setExtractResult(result);
        setExtractRevision((prev) => prev + 1);
        setHasChanges(false);
      } catch (err) {
        addSnackbar({ message: (err as Error).message, variant: 'danger' });
      }
    },
    [agentId, threadId, file.name, simpleExtract, addSnackbar, setCurrentConfiguratorSchema],
  );

  const handleReExtract = useCallback(
    async (updatedSchema: ExtractionSchemaPayload, prompt: string) => {
      try {
        const result = await simpleExtract({
          agentId,
          threadId,
          fileRef: file.name,
          extractionSchema: updatedSchema,
          prompt: prompt || undefined,
        });

        // Update current schema
        setCurrentConfiguratorSchema(updatedSchema);
        setExtractResult(result);
        setExtractRevision((prev) => prev + 1);
        setHasChanges(false);
      } catch (err) {
        addSnackbar({ message: (err as Error).message, variant: 'danger' });
        throw err;
      }
    },
    [agentId, threadId, file.name, simpleExtract, addSnackbar, setCurrentConfiguratorSchema],
  );

  /**
   * Need to persist schema state as is without any transformations in the middle and use it in schema editor
   * - with any transformations in the middle the inputs will start to loose focus as new entry will be passed down
   */
  const handleConfiguratorSchemaChange = useCallback(
    (updatedSchema: ConfigurationSchema) => {
      setConfiguratorSchema(updatedSchema);

      const description = currentSchema?.description;
      const apiSchema = toJSONDocumentSchema(
        updatedSchema?.children as RenderedField[],
        description ? String(description) : '',
      );
      setCurrentSchema(apiSchema as ExtractionSchemaPayload);

      setHasChanges(true);
    },
    [currentSchema],
  );

  const handleSchemaChange = useCallback((updatedSchema: ExtractionSchemaPayload | null) => {
    setCurrentSchema(updatedSchema);
  }, []);

  // Initialize from existing schema and extract result (e.g., from thread state)
  const initializeFromExisting = useCallback(
    (schemaResponse: ExtractSchemaResponse, extractResponse: SimpleExtractResponse) => {
      setCurrentSchema(schemaResponse.schema as ExtractionSchemaPayload);
      setExtractResult(extractResponse);
      setUserPrompt(parseUserInstructions(schemaResponse.user_prompt));
    },
    [],
  );

  const error = schemaError?.message || extractError?.message || null;

  return {
    // State
    extractResult,
    currentSchema,
    configuratorSchema,
    hasChanges,
    extractRevision,
    extractedDataWithCitations,
    userPrompt,
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
    handleConfiguratorSchemaChange,
    initializeFromExisting,
    setHasChanges,
  };
};
