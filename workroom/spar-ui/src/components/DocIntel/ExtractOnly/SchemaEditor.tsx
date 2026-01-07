import { FC, useState, useEffect } from 'react';
import { Box, Typography } from '@sema4ai/components';
import type { ExtractionSchemaPayload } from '../shared/types';

import { RenderedField, toRenderedDocumentSchema } from '../shared/utils/schema-lib';

/**
 * SchemaEditor - Visual schema builder/editor
 */
interface SchemaEditorProps {
  schema: ExtractionSchemaPayload | null;
  // eslint-disable-next-line react/no-unused-prop-types -- TODO: Valters will use when DataConfigurator is integrated
  onChange?: (schema: ExtractionSchemaPayload) => void;
  // eslint-disable-next-line react/no-unused-prop-types -- TODO: Valters will use when DataConfigurator is integrated
  disabled?: boolean;
}

export const SchemaEditor: FC<SchemaEditorProps> = (props) => {
  const { schema } = props;
  // TODO: Valters - use props.onChange and props.disabled when DataConfigurator is integrated

  const [fields, setFields] = useState<RenderedField[]>([]);
  const [schemaDescription, setSchemaDescription] = useState<string | undefined>();

  useEffect(() => {
    if (schema) {
      const result = toRenderedDocumentSchema(schema);
      if (result.success) {
        setFields(result.data.fields);
        setSchemaDescription(result.data.description);
      }
    }
  }, [schema]);

  if (!schema) {
    return (
      <Box display="flex" flexDirection="column" height="100%">
        <Box
          padding="$12 $16"
          display="flex"
          alignItems="center"
          justifyContent="space-between"
          style={{ borderBottom: '1px solid var(--sema4ai-colors-border-subtle)' }}
        >
          <Typography fontSize="$14" fontWeight="bold">
            Extraction Schema
          </Typography>
        </Box>
        <Box padding="$16" display="flex" alignItems="center" justifyContent="center">
          <Typography color="content.subtle">No schema loaded</Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column" height="100%">
      {/* Content */}
      <Box flex="1" overflow="auto" minHeight="0" padding="$16">
        <Box display="flex" flexDirection="column" gap="$12">
          {/* Schema metadata */}
          {typeof schema.title === 'string' && schema.title && (
            <Typography fontSize="$16" fontWeight="bold">
              {schema.title}
            </Typography>
          )}
          {schemaDescription && (
            <Typography fontSize="$14" color="content.subtle">
              {schemaDescription}
            </Typography>
          )}
          {/*
           * TODO: Valters - DataConfigurator integration
           *
           * Available:
           * - fields: RenderedField[] (compatible with FieldData)
           * - handleFieldsChange: (fields: RenderedField[]) => void
           * - disabled: boolean
           *
           * Example usage:
           * <DataConfigurator
           *   schema={{ columns: ['Name', 'Type', 'Description'], withActions: !disabled, fields }}
           *   onSchemaChange={(s) => handleFieldsChange(s.fields)}
           *   draggable={!disabled}
           *   renderRow={SchemaRenderRow}
           * />
           */}
          <Box>
            <Typography color="content.subtle">DataConfigurator placeholder ({fields.length} fields)</Typography>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};
