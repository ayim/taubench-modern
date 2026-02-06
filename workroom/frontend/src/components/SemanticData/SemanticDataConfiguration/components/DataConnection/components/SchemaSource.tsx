import { useCallback, useContext, useEffect, useState } from 'react';
import { Box, Button, Code, Dialog, Input, Link, Typography, useDebounce, useSnackbar } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';

import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import { useValidateJsonSchemaMutation } from '../../../../../../queries/semanticData';
import { ConfigurationStepView, DataConnectionFormContext, DataConnectionFormSchema, SchemaFormItem } from '../../form';
import { SchemaList } from './SchemaList';

type SchemaValidationError = {
  path: string;
  message: string;
};

const normalizeSchemaName = (name: string): string => {
  return name.trim().replace(/ /g, '_');
};

const isValidSchemaName = (name: string): boolean => {
  return /^[a-zA-Z0-9_ ]*$/.test(name);
};

export const SchemaSource: ConfigurationStepView = ({ onClose }) => {
  const { addSnackbar } = useSnackbar();
  const { setValue, watch } = useFormContext<DataConnectionFormSchema>();
  const schemas = watch('schemas') || [];
  const { mutateAsync: validateSchema } = useValidateJsonSchemaMutation({});
  const { onSubmit } = useContext(DataConnectionFormContext);

  const [jsonText, setJsonText] = useState('{\n  "type": "object",\n  "properties": {}\n}');
  const [schemaName, setSchemaName] = useState('');
  const [schemaDescription, setSchemaDescription] = useState('');
  const [validationErrors, setValidationErrors] = useState<SchemaValidationError[]>([]);
  const [jsonParseError, setJsonParseError] = useState<string | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  const debouncedJsonText = useDebounce(jsonText, 500);

  useEffect(() => {
    const validateJsonSchema = async () => {
      // First try to parse as JSON
      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(debouncedJsonText);
        setJsonParseError(null);
      } catch {
        setJsonParseError('Invalid JSON syntax');
        setValidationErrors([]);
        return;
      }

      // Then validate with backend
      setIsValidating(true);
      try {
        const result = await validateSchema({ json_schema: parsed });
        setValidationErrors(result.errors || []);
      } catch {
        addSnackbar({
          message: 'Failed to validate schema',
          variant: 'danger',
        });
      } finally {
        setIsValidating(false);
      }
    };

    validateJsonSchema();
  }, [debouncedJsonText, validateSchema, addSnackbar]);

  const handleJsonChange = useCallback((value: string) => {
    setJsonText(value);
  }, []);

  const handleAddSchema = useCallback(() => {
    if (jsonParseError || validationErrors.length > 0) {
      return;
    }

    const addNormalizedName = normalizeSchemaName(schemaName);

    if (!addNormalizedName) {
      addSnackbar({ message: 'Schema name is required', variant: 'danger' });
      return;
    }

    if (!isValidSchemaName(schemaName)) {
      addSnackbar({ message: 'Only letters, numbers, underscores, and spaces are allowed', variant: 'danger' });
      return;
    }

    if (schemas.some((schema) => schema.name.toLowerCase() === addNormalizedName.toLowerCase())) {
      addSnackbar({ message: 'A Schema with this name already exists in this Semantic Data Model', variant: 'danger' });
      return;
    }

    if (!schemaDescription.trim()) {
      addSnackbar({ message: 'Schema description is required', variant: 'danger' });
      return;
    }

    try {
      const parsed = JSON.parse(jsonText);
      const newSchema: SchemaFormItem = {
        name: addNormalizedName,
        description: schemaDescription.trim(),
        json_schema: parsed,
        validations: [],
        transformations: [],
      };

      setValue('schemas', [...schemas, newSchema]);

      // Reset form
      setJsonText('{\n  "type": "object",\n  "properties": {}\n}');
      setSchemaName('');
      setSchemaDescription('');
      setValidationErrors([]);

      addSnackbar({ message: 'Schema added', variant: 'success' });
    } catch {
      addSnackbar({ message: 'Failed to add schema', variant: 'danger' });
    }
  }, [jsonText, schemaName, schemaDescription, schemas, setValue, addSnackbar, jsonParseError, validationErrors]);

  const handleRemoveSchema = useCallback(
    (index: number) => {
      const newSchemas = schemas.filter((_, i) => i !== index);
      setValue('schemas', newSchemas);
    },
    [schemas, setValue],
  );

  const hasErrors = !!jsonParseError || validationErrors.length > 0;
  const errorMessage = jsonParseError || validationErrors.map((e) => e.message).join('; ');
  const trimmedName = schemaName.trim();
  const hasInvalidChars = trimmedName.length > 0 && !isValidSchemaName(schemaName);
  const normalizedName = normalizeSchemaName(schemaName);
  const isDuplicateName =
    normalizedName.length > 0 && schemas.some((schema) => schema.name.toLowerCase() === normalizedName.toLowerCase());

  const getStatusMessage = () => {
    if (hasErrors) return errorMessage;
    if (isValidating) return 'Validating...';
    return 'Valid JSON Schema';
  };

  return (
    <>
      <Dialog.Content maxWidth={768}>
        <Typography variant="display-medium" mb="$12">
          Add Schemas
        </Typography>
        <Typography variant="body-large" color="content.subtle" mb="$40">
          Define JSON schemas to validate and structure data for your agent. You can add multiple schemas before
          creating the semantic data model.{' '}
          <Link href={EXTERNAL_LINKS.SEMANTIC_DATA_MODELS} target="_blank">
            Learn more
          </Link>
        </Typography>

        <Box mb="$16">
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

        <Box mb="$16">
          <Input
            label="Description"
            value={schemaDescription}
            onChange={(e) => setSchemaDescription(e.target.value)}
            placeholder="Describe what this schema represents"
            required
          />
        </Box>

        <Box mb="$16">
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
            rows={8}
          />
          <Typography variant="body-small" color={hasErrors ? 'content.danger' : 'content.subtle'} mt="$4">
            {getStatusMessage()}
          </Typography>
        </Box>

        <Button
          type="button"
          onClick={handleAddSchema}
          disabled={hasErrors || !trimmedName || hasInvalidChars || isDuplicateName || !schemaDescription.trim()}
          variant="secondary"
          round
        >
          Add Schema
        </Button>

        {schemas.length > 0 && <SchemaList schemas={schemas} onRemoveSchema={handleRemoveSchema} />}
      </Dialog.Content>

      <Dialog.Actions>
        <Button type="button" onClick={onSubmit} disabled={schemas.length === 0} round>
          {`Create SDM (${schemas.length} schema${schemas.length !== 1 ? 's' : ''})`}
        </Button>
        <Button variant="secondary" round onClick={onClose}>
          Cancel
        </Button>
      </Dialog.Actions>
    </>
  );
};
