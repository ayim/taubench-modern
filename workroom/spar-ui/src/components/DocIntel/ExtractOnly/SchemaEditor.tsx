import { FC } from 'react';
import { Box, Typography } from '@sema4ai/components';
import { SchemaConfigurator } from '@sema4ai/layouts';
import type { ConfigurationSchema } from '../shared/utils/schema-lib';

/**
 * SchemaEditor - Visual schema builder/editor
 * Wraps SchemaConfigurator from @sema4ai/layouts
 */
interface SchemaEditorProps {
  schema: ConfigurationSchema | null;
  onChange?: (schema: ConfigurationSchema) => void;
  disabled?: boolean;
}

export const SchemaEditor: FC<SchemaEditorProps> = ({ schema, onChange, disabled }) => {
  if (!schema) {
    return (
      <Box display="flex" flexDirection="column" height="100%" gap="$8" padding="$16">
        <Typography fontSize="$14" fontWeight="bold">
          Extraction Schema
        </Typography>

        <Box padding="$16" display="flex" alignItems="center" justifyContent="center" minHeight="400px">
          <Typography color="content.subtle">No schema loaded</Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box display="flex" flexDirection="column" height="100%">
      <Box flex="1" overflow="auto" minHeight="0" padding="$16">
        <Box display="flex" flexDirection="column" gap="$8">
          <Typography fontSize="$14" fontWeight="bold">
            Extraction Schema
          </Typography>

          {schema.description && (
            <Typography fontSize="$14" color="content.subtle" mt="$4">
              {schema.description}
            </Typography>
          )}

          <SchemaConfigurator
            schema={schema as Extract<ConfigurationSchema, { type: 'object' }>}
            onSchemaChange={disabled ? undefined : onChange}
          />
        </Box>
      </Box>
    </Box>
  );
};
