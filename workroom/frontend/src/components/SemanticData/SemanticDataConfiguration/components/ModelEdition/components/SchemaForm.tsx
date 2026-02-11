import { FC, useState, useEffect, useCallback } from 'react';
import { Box, Code, Input, Link, Typography, useDebounce } from '@sema4ai/components';
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

  const handleJsonChange = useCallback((value: string) => {
    setJsonText(value);
  }, []);

  const hasErrors = !!jsonParseError || validationErrors.length > 0;
  const errorMessage = jsonParseError || validationErrors.map((e) => e.message).join('; ');
  const trimmedName = schemaName.trim();
  const hasInvalidChars = trimmedName.length > 0 && !isValidSchemaName(schemaName);
  const normalizedName = normalizeSchemaName(schemaName);
  const isDuplicateName =
    normalizedName.length > 0 &&
    schemas.some((s, i) => s.name.toLowerCase() === normalizedName.toLowerCase() && (!isEditMode || i !== schemaIndex));

  const isFormValid =
    !hasErrors &&
    !hasInvalidChars &&
    !isDuplicateName &&
    !isValidating &&
    trimmedName.length > 0 &&
    schemaDescription.trim().length > 0;

  // Notify parent of form data and validity changes
  useEffect(() => {
    onFormDataChange({ name: schemaName, description: schemaDescription, jsonText }, isFormValid);
  }, [schemaName, schemaDescription, jsonText, isFormValid, onFormDataChange]);

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
        <Typography variant="body-small" color={hasErrors ? 'content.danger' : 'content.subtle'} mt="$4">
          {getStatusMessage()}
        </Typography>
      </Box>
    </Box>
  );
};
