import { useCallback, useContext, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { IconInformation, IconPencil, IconPlus } from '@sema4ai/icons';
import { Box, Button, Dialog, Typography, Link, Banner, Tabs } from '@sema4ai/components';

import { RenameDialog } from '~/components/dialogs/RenameDialog';
import { EXTERNAL_LINKS } from '~/lib/constants';
import { ConfigurationStep, ConfigurationStepView, DataConnectionFormContext, DataConnectionFormSchema } from '../form';
import { ValidationErrorBanner } from '../ValidationErrorBanner';
import { getTableDimensions } from '../../../../../lib/SemanticDataModels';
import { TableTree } from './components/TableTree';
import { ModelScore } from './components/ModelScore';
import { VerifiedQueriesTable } from './components/VerifiedQueriesTable';
import { SchemasTable } from './components/SchemasTable';
import { BusinessContext } from './components/BusinessContext';
import { InlineEditor } from './components/InlineEditor';
import { SchemaForm } from './components/SchemaForm';
import { VerifiedQueryForm } from './components/VerifiedQueryForm';
import { useSchemaEditor } from './hooks/useSchemaEditor';
import { useVerifiedQueryEditor } from './hooks/useVerifiedQueryEditor';

type EditMode = { type: 'none' } | { type: 'schema'; index?: number } | { type: 'verified-query'; index?: number };

type Props = {
  modelId: string;
};

export const ModelEdition: ConfigurationStepView<Props> = ({ modelId, onClose, setActiveStep }) => {
  const [activeTab, setActiveTab] = useState<number>(1);
  const { watch, setValue } = useFormContext<DataConnectionFormSchema>();
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const [editMode, setEditMode] = useState<EditMode>({ type: 'none' });

  const { databaseInspectionState, validationErrors } = useContext(DataConnectionFormContext);

  const handleBack = useCallback(() => {
    setEditMode({ type: 'none' });
  }, []);

  const schemaEditor = useSchemaEditor({
    index: editMode.type === 'schema' ? editMode.index : undefined,
    onDone: handleBack,
  });

  const queryEditor = useVerifiedQueryEditor({
    index: editMode.type === 'verified-query' ? editMode.index : undefined,
    modelId,
    onDone: handleBack,
  });

  const onToggleRenameDialog = () => {
    setIsRenameDialogOpen(!isRenameDialogOpen);
  };

  const onModelRename = (newName: string) => {
    setValue('name', newName);
    setIsRenameDialogOpen(false);
  };

  const { name, dataSelection, dataConnectionId, schemas, tables } = watch();

  const hasDisplayableTableContent = tables && tables.some((table) => getTableDimensions(table).length > 0);

  if (editMode.type === 'schema') {
    return (
      <InlineEditor {...schemaEditor.editorProps}>
        <SchemaForm
          initialSchema={schemaEditor.editingSchema}
          schemaIndex={editMode.index}
          onFormDataChange={schemaEditor.handleFormDataChange}
        />
      </InlineEditor>
    );
  }

  if (editMode.type === 'verified-query') {
    return (
      <InlineEditor {...queryEditor.editorProps}>
        <VerifiedQueryForm
          isNewQuery={editMode.index === undefined}
          initialQuery={queryEditor.editingQuery}
          semanticDataModel={queryEditor.semanticDataModel}
          verifyMutation={queryEditor.verifyMutation}
          onFormDataChange={queryEditor.handleFormDataChange}
          onValidationErrorsChange={queryEditor.handleValidationErrorsChange}
          errors={queryEditor.verifiedQueryErrors}
        />
      </InlineEditor>
    );
  }

  return (
    <>
      <Dialog.Content>
        <Box display="flex" flexDirection="column" gap="$16" height="100%">
          {databaseInspectionState.error && (
            <Banner
              message="Connection Failed"
              variant="error"
              icon={IconInformation}
              description={
                <>
                  Unable to connect to the database. Please check your configuration settings.{' '}
                  <Link
                    as="button"
                    type="button"
                    variant="secondary"
                    onClick={() => setActiveStep(ConfigurationStep.DataConnection)}
                  >
                    Configure Connection
                  </Link>
                </>
              }
            />
          )}
          {validationErrors.length > 0 && <ValidationErrorBanner errors={validationErrors} />}
          <Box display="flex" flexDirection={['column', 'column', 'column', 'row']} gap="$8" mb="$16" width="100%">
            <Box display="flex" flexDirection="column" gap="$8">
              <Box display="flex" alignItems="center" gap="$8">
                <Typography variant="display-medium">{name}</Typography>
                <Button
                  variant="ghost-subtle"
                  size="small"
                  icon={IconPencil}
                  aria-label="Edit Model Name"
                  onClick={onToggleRenameDialog}
                />
              </Box>
              <Box display="flex" alignItems="center" gap="$8" maxWidth={860}>
                <Typography variant="body-large" color="content.subtle">
                  Review your data model and add details to improve how your agent understands the data. Use
                  descriptions and synonyms to clarify meaning, provide business context, and make the data easier for
                  the agent to work with.{' '}
                  <Link href={EXTERNAL_LINKS.SEMANTIC_DATA_MODELS} target="_blank">
                    Learn more
                  </Link>
                </Typography>
              </Box>
            </Box>
            <Box ml={[0, 0, 0, 'auto']}>
              <ModelScore />
            </Box>
          </Box>
          <Tabs display="flex" flexDirection="column" flex="1" activeTab={activeTab} setActiveTab={setActiveTab}>
            <Tabs.Tab>Business Context</Tabs.Tab>
            <Tabs.Tab>Data Model</Tabs.Tab>
            <Tabs.Tab>Verified Queries</Tabs.Tab>
            <Tabs.Tab>Schemas</Tabs.Tab>
            <Tabs.Panel>
              <BusinessContext />
            </Tabs.Panel>

            <Tabs.Panel>
              {hasDisplayableTableContent && (
                <Box display="flex" gap="$8" mb="$16">
                  {dataConnectionId && (
                    <Button
                      variant="secondary"
                      onClick={() => setActiveStep(ConfigurationStep.DataSelection)}
                      icon={IconPlus}
                      round
                    >
                      Add Data
                    </Button>
                  )}
                </Box>
              )}
              <TableTree
                modelId={modelId}
                emptyAction={
                  dataConnectionId ? (
                    <Button
                      variant="secondary"
                      onClick={() => setActiveStep(ConfigurationStep.DataSelection)}
                      icon={IconPlus}
                      round
                    >
                      Add Data
                    </Button>
                  ) : undefined
                }
              />
            </Tabs.Panel>
            <Tabs.Panel flex="1">
              <VerifiedQueriesTable
                onCreateQuery={() => setEditMode({ type: 'verified-query' })}
                onEditQuery={(index) => setEditMode({ type: 'verified-query', index })}
              />
            </Tabs.Panel>
            <Tabs.Panel flex="1">
              <SchemasTable
                onCreateSchema={() => setEditMode({ type: 'schema' })}
                onEditSchema={(index) => setEditMode({ type: 'schema', index })}
              />
            </Tabs.Panel>
          </Tabs>
        </Box>
      </Dialog.Content>
      <Dialog.Actions>
        <Button disabled={dataSelection.length === 0 && schemas.length === 0} type="submit" round>
          Continue
        </Button>
        <Button variant="secondary" onClick={onClose} round>
          Cancel
        </Button>
      </Dialog.Actions>

      {isRenameDialogOpen && (
        <RenameDialog
          onClose={onToggleRenameDialog}
          onRename={onModelRename}
          entityName={name || ''}
          entityType="Model Name"
        />
      )}
    </>
  );
};
