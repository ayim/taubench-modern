/* eslint-disable jsx-a11y/anchor-is-valid */
import { useContext, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { IconInformation, IconPencil, IconPlus } from '@sema4ai/icons';
import { Box, Button, Dialog, Typography, Link, Banner, Tabs } from '@sema4ai/components';

import { RenameDialog } from '../../../../../common/dialogs/RenameDialog';
import { EXTERNAL_LINKS } from '../../../../../lib/constants';
import { ConfigurationStep, ConfigurationStepView, DataConnectionFormContext, DataConnectionFormSchema } from '../form';
import { TableTree } from './components/TableTree';
import { ModelScore } from './components/ModelScore';
import { VerifiedQueriesTable } from './components/VerifiedQueriesTable';
import { BusinessContext } from './components/BusinessContext';

type Props = {
  modelId: string;
};

export const ModelEdition: ConfigurationStepView<Props> = ({ modelId, onClose, setActiveStep }) => {
  const [activeTab, setActiveTab] = useState<number>(1);
  const { watch, setValue } = useFormContext<DataConnectionFormSchema>();
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);

  const { databaseInspectionState } = useContext(DataConnectionFormContext);

  const onToggleRenameDialog = () => {
    setIsRenameDialogOpen(!isRenameDialogOpen);
  };

  const onModelRename = (newName: string) => {
    setValue('name', newName);
    setIsRenameDialogOpen(false);
  };

  const { name, dataSelection, dataConnectionId } = watch();

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
                  <Link href={EXTERNAL_LINKS.DATA_ACCESS} target="_blank">
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
            <Tabs.Panel>
              <BusinessContext />
            </Tabs.Panel>

            <Tabs.Panel>
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
              <TableTree modelId={modelId} />
            </Tabs.Panel>
            <Tabs.Panel flex="1">
              <VerifiedQueriesTable modelId={modelId} />
            </Tabs.Panel>
          </Tabs>
        </Box>
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
    </>
  );
};
