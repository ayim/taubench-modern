/* eslint-disable jsx-a11y/anchor-is-valid */
import { useContext, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { Box, Button, Dialog, Typography, Link, Banner } from '@sema4ai/components';
import { IconInformation, IconPencil, IconWriteNote } from '@sema4ai/icons';

import { RenameDialog } from '../../../../../common/dialogs/RenameDialog';
import { EXTERNAL_LINKS } from '../../../../../lib/constants';
import { ConfigurationStep, ConfigurationStepView, DataConnectionFormContext, DataConnectionFormSchema } from '../form';
import { TableTree } from './components/TableTree';
import { ModelScore } from './components/ModelScore';

type Props = {
  modelId: string;
};

export const ModelEdition: ConfigurationStepView<Props> = ({ modelId, onClose, setActiveStep }) => {
  const { watch, setValue } = useFormContext<DataConnectionFormSchema>();
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const [isUpdateContextDialogOpen, setIsUpdateContextDialogOpen] = useState(false);
  const { databaseInspectionState } = useContext(DataConnectionFormContext);

  const onToggleRenameDialog = () => {
    setIsRenameDialogOpen(!isRenameDialogOpen);
  };

  const onToggleUpdateContextDialog = () => {
    setIsUpdateContextDialogOpen(!isUpdateContextDialogOpen);
  };

  const onModelRename = (newName: string) => {
    setValue('name', newName);
    setIsRenameDialogOpen(false);
  };

  const onModelUpdateContext = (newContext: string) => {
    setValue('description', newContext);
    setIsUpdateContextDialogOpen(false);
  };

  const { name, description, dataSelection } = watch();

  return (
    <>
      <Dialog.Content>
        {databaseInspectionState.error && (
          <Banner
            message="Connection Failed"
            variant="error"
            icon={IconInformation}
            description={
              <>
                Unable to connect to the Call Center database. Please check your configuration settings.{' '}
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
        <Box display="flex" mb="$40" width="100%">
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
            <Box display="flex" alignItems="center" gap="$8" maxWidth={720}>
              <Typography variant="body-large" color="content.subtle">
                Review your data model and add details to improve how your agent understands the data. Use descriptions
                and synonyms to clarify meaning, provide business context, and make the data easier for the agent to
                work with.{' '}
                <Link href={EXTERNAL_LINKS.DATA_ACCESS} target="_blank">
                  Learn more
                </Link>
              </Typography>
            </Box>
          </Box>
          <Box ml="auto">
            <ModelScore />
          </Box>
        </Box>
        <Box display="flex" gap="$8" mb="$16">
          <Button variant="secondary" onClick={onToggleUpdateContextDialog} icon={IconWriteNote} round>
            Edit Business Context
          </Button>
        </Box>
        <TableTree modelId={modelId} />
      </Dialog.Content>
      <Dialog.Actions>
        <Button disabled={dataSelection.length === 0} type="submit" round>
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

      {isUpdateContextDialogOpen && (
        <RenameDialog
          onClose={onToggleUpdateContextDialog}
          onRename={onModelUpdateContext}
          entityName={description || ''}
          actionType="Update"
          actionDescription="Describe the data structure and its business context."
          entityType="Business Context"
          multiLine
        />
      )}
    </>
  );
};
