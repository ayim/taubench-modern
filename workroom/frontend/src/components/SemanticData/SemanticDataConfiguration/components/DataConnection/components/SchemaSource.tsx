import { useCallback, useContext, useState } from 'react';
import { Box, Button, Dialog, Link, Typography } from '@sema4ai/components';
import { IconPlus } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';

import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import { ConfigurationStepView, DataConnectionFormContext, DataConnectionFormSchema } from '../../form';
import { SchemaList } from './SchemaList';
import { SchemaForm, SCHEMA_FORM_MAX_WIDTH } from '../../ModelEdition/components/SchemaForm';
import { InlineEditor } from '../../ModelEdition/components/InlineEditor';
import { useSchemaEditor } from '../../ModelEdition/hooks/useSchemaEditor';

type EditState = { type: 'list' } | { type: 'schema'; index?: number };

export const SchemaSource: ConfigurationStepView = ({ onClose }) => {
  const { setValue, watch } = useFormContext<DataConnectionFormSchema>();
  const schemas = watch('schemas') || [];
  const { onSubmit } = useContext(DataConnectionFormContext);

  const [editState, setEditState] = useState<EditState>({ type: 'list' });

  const handleBack = useCallback(() => {
    setEditState({ type: 'list' });
  }, []);

  const schemaEditor = useSchemaEditor({
    index: editState.type === 'schema' ? editState.index : undefined,
    onDone: handleBack,
  });

  const handleRemoveSchema = useCallback(
    (index: number) => {
      const newSchemas = schemas.filter((_, i) => i !== index);
      setValue('schemas', newSchemas);
    },
    [schemas, setValue],
  );

  if (editState.type === 'schema') {
    return (
      <InlineEditor {...schemaEditor.editorProps} contentMaxWidth={SCHEMA_FORM_MAX_WIDTH}>
        <SchemaForm
          initialSchema={schemaEditor.editingSchema}
          schemaIndex={editState.index}
          onFormDataChange={schemaEditor.handleFormDataChange}
        />
      </InlineEditor>
    );
  }

  return (
    <>
      <Dialog.Content maxWidth={SCHEMA_FORM_MAX_WIDTH}>
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
          <Button
            type="button"
            onClick={() => setEditState({ type: 'schema' })}
            variant="secondary"
            icon={IconPlus}
            round
          >
            Add Schema
          </Button>
        </Box>

        {schemas.length > 0 && (
          <SchemaList
            schemas={schemas}
            onRemoveSchema={handleRemoveSchema}
            onEditSchema={(index) => setEditState({ type: 'schema', index })}
          />
        )}
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
