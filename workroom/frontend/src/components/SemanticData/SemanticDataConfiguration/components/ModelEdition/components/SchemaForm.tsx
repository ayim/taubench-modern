import { FC, useState, useEffect, useCallback } from 'react';
import { Box, Code, Input, Link, Switch, Typography, useDebounce } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { useValidateJsonSchemaMutation } from '~/queries/semanticData';
import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import { DataConnectionFormSchema, SchemaFormItem } from '../../form';
import { normalizeSchemaName, isValidSchemaName } from '../../schemaHelpers';

type SchemaValidationError = {
  path: string;
  message: string;
};

export type SchemaFormData = {
  name: string;
  description: string;
  jsonText: string;
  useDocumentExtraction: boolean;
  systemPrompt: string;
  configurationText: string;
};

type Props = {
  initialSchema?: SchemaFormItem;
  schemaIndex?: number;
  onFormDataChange: (data: SchemaFormData, isValid: boolean) => void;
};

const DEFAULT_JSON_SCHEMA = '{\n  "type": "object",\n  "properties": {}\n}';

export const SCHEMA_FORM_MAX_WIDTH = 768;

export const SchemaForm: FC<Props> = ({ initialSchema, schemaIndex, onFormDataChange }) => {
  const { watch } = useFormContext<DataConnectionFormSchema>();
  const { mutateAsync: validateSchema } = useValidateJsonSchemaMutation({});
  const schemas = watch('schemas') || [];

  const isEditMode = schemaIndex !== undefined && initialSchema !== undefined;

  const [schemaName, setSchemaName] = useState(initialSchema?.name || '');
  const [schemaDescription, setSchemaDescription] = useState(initialSchema?.description || '');
  const [jsonText, setJsonText] = useState(
    initialSchema ? JSON.stringify(initialSchema.json_schema, null, 2) : DEFAULT_JSON_SCHEMA,
  );
  const [validationErrors, setValidationErrors] = useState<SchemaValidationError[]>([]);
  const [jsonParseError, setJsonParseError] = useState<string | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  const [useDocumentExtraction, setUseDocumentExtraction] = useState(initialSchema?.document_extraction != null);
  const [systemPrompt, setSystemPrompt] = useState(initialSchema?.document_extraction?.system_prompt ?? '');
  const [configurationText, setConfigurationText] = useState(() => {
    const config = initialSchema?.document_extraction?.configuration;
    if (config && Object.keys(config).length > 0) {
      return JSON.stringify(config, null, 2);
    }
    return '{}';
  });
  const [configJsonError, setConfigJsonError] = useState<string | null>(null);

  const debouncedJsonText = useDebounce(jsonText, 500);

  useEffect(() => {
    const validateJsonSchema = async (): Promise<void> => {
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(debouncedJsonText);
        setJsonParseError(null);
      } catch {
        setJsonParseError('Invalid JSON syntax');
        setValidationErrors([]);
        return;
      }

      setIsValidating(true);
      try {
        const result = await validateSchema({ json_schema: parsed });
        setValidationErrors(result.errors || []);
      } catch (error) {
        console.error('Schema validation request failed:', error);
      } finally {
        setIsValidating(false);
      }
    };

    validateJsonSchema();
  }, [debouncedJsonText, validateSchema]);

  useEffect(() => {
    if (!useDocumentExtraction || !configurationText.trim()) {
      setConfigJsonError(null);
      return;
    }
    try {
      JSON.parse(configurationText);
      setConfigJsonError(null);
    } catch {
      setConfigJsonError('Invalid JSON syntax');
    }
  }, [configurationText, useDocumentExtraction]);

  const handleJsonChange = useCallback((value: string) => {
    setJsonText(value);
  }, []);

  const handleConfigChange = useCallback((value: string) => {
    setConfigurationText(value);
  }, []);

  const hasErrors = !!jsonParseError || validationErrors.length > 0;
  const errorMessage = jsonParseError || validationErrors.map((e) => e.message).join('; ');
  const trimmedName = schemaName.trim();
  const hasInvalidChars = trimmedName.length > 0 && !isValidSchemaName(schemaName);
  const normalizedName = normalizeSchemaName(schemaName);
  const isDuplicateName =
    normalizedName.length > 0 &&
    schemas.some((s, i) => s.name.toLowerCase() === normalizedName.toLowerCase() && (!isEditMode || i !== schemaIndex));
  const hasDIConfigError = useDocumentExtraction && configJsonError;

  const isFormValid =
    !hasErrors &&
    !hasInvalidChars &&
    !isDuplicateName &&
    !isValidating &&
    trimmedName.length > 0 &&
    schemaDescription.trim().length > 0 &&
    !hasDIConfigError;

  // Notify parent of form data and validity changes
  useEffect(() => {
    onFormDataChange(
      {
        name: schemaName,
        description: schemaDescription,
        jsonText,
        useDocumentExtraction,
        systemPrompt,
        configurationText,
      },
      isFormValid,
    );
  }, [
    schemaName,
    schemaDescription,
    jsonText,
    useDocumentExtraction,
    systemPrompt,
    configurationText,
    isFormValid,
    onFormDataChange,
  ]);

  const getStatusMessage = (): string => {
    if (hasErrors) return errorMessage || '';
    if (isValidating) return 'Validating...';
    return 'Valid JSON Schema';
  };

  return (
    <Box display="flex" flexDirection="column" gap="$16" maxWidth={SCHEMA_FORM_MAX_WIDTH} mx="auto" width="100%">
      <Typography variant="body-large" color="content.subtle">
        Define a JSON schema to validate and structure data for your agent.{' '}
        <Link href={EXTERNAL_LINKS.SEMANTIC_DATA_MODELS} target="_blank">
          Learn more
        </Link>
      </Typography>

      <Box>
        <Input
          label="Schema Name"
          value={schemaName}
          onChange={(e) => setSchemaName(e.target.value)}
          placeholder="e.g., Invoice, Customer, Order"
          required
        />
        {hasInvalidChars && (
          <Typography variant="body-small" color="content.danger" mt="$4">
            Only letters, numbers, underscores, and spaces are allowed
          </Typography>
        )}
        {!hasInvalidChars && isDuplicateName && (
          <Typography variant="body-small" color="content.danger" mt="$4">
            A schema with this name already exists
          </Typography>
        )}
      </Box>

      <Input
        label="Description"
        value={schemaDescription}
        onChange={(e) => setSchemaDescription(e.target.value)}
        placeholder="Describe what this schema represents"
        required
      />

      <Box>
        <Typography fontWeight="medium" mb="$8">
          JSON Schema
        </Typography>
        <Code
          value={jsonText}
          onChange={handleJsonChange}
          lang="json"
          title="JSON"
          aria-label="JSON Schema"
          placeholder='{"type": "object", "properties": {}}'
          rows={12}
        />
      </Box>
      <Typography variant="body-small" color={hasErrors ? 'content.danger' : 'content.subtle'}>
        {getStatusMessage()}
      </Typography>

      <Box>
        <Box display="flex" alignItems="center" gap="$8" mb="$8">
          <Switch
            aria-label="Use with Document Intelligence"
            checked={useDocumentExtraction}
            onChange={(e) => setUseDocumentExtraction(e.target.checked)}
          />
          <Typography fontWeight="medium">Use with Document Intelligence</Typography>
        </Box>
        <Typography variant="body-small" color="content.subtle">
          Enable to configure how this schema is used with Document Intelligence for data extraction.
        </Typography>
      </Box>

      {useDocumentExtraction && (
        <Box display="flex" flexDirection="column" gap="$16">
          <Input
            label="System Prompt"
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            placeholder="Optional prompt to guide the extraction model"
            rows={4}
          />

          <Box>
            <Typography fontWeight="medium" mb="$8">
              Advanced Configuration
            </Typography>
            <Code
              value={configurationText}
              onChange={handleConfigChange}
              lang="json"
              title="Advanced Configuration JSON"
              aria-label="Advanced Configuration"
              placeholder="{}"
              rows={6}
            />
            {configJsonError && (
              <Typography variant="body-small" color="content.danger" mt="$4">
                {configJsonError}
              </Typography>
            )}
          </Box>
        </Box>
      )}
    </Box>
  );
};
