import { FC, useEffect } from 'react';
import { Button, Dialog, Form, Progress, useSnackbar } from '@sema4ai/components';
import { DataConnection } from '@sema4ai/data-interface';
import { zodResolver } from '@hookform/resolvers/zod';
import { FormProvider, Resolver, useForm } from 'react-hook-form';

import { useDataConnectionQuery, useUpdateDataConnectionMutation } from '../../../../queries';
import { DataConnectionForm } from './DataConnectionForm';

type Props = {
  onClose: () => void;
  dataConnectionId: string;
  snowflakeLinkedUser?: string;
};

// Agent Server returns all fields, including unconfigured fields with `null` value, which will fail form validation
const removeConfigurationNullValues = (dataConnection: DataConnection) => {
  return {
    ...dataConnection,
    configuration: Object.fromEntries(
      Object.entries(dataConnection.configuration).filter(([, value]) => value !== null),
    ),
  };
};

export const UpdateDataConnection: FC<Props> = ({ dataConnectionId, snowflakeLinkedUser, onClose }) => {
  const { addSnackbar } = useSnackbar();
  const { mutateAsync: updateDataConnectionAsync, isPending } = useUpdateDataConnectionMutation({ dataConnectionId });
  const { data: dataConnection, isFetching } = useDataConnectionQuery({ dataConnectionId });

  const formMethods = useForm<DataConnection>({
    resolver: zodResolver(DataConnection) as Resolver<DataConnection>,
    defaultValues: {},
  });

  useEffect(() => {
    if (dataConnection) {
      formMethods.reset(removeConfigurationNullValues(dataConnection));
    }
  }, [dataConnection]);

  const onSubmit = formMethods.handleSubmit(async (values) => {
    updateDataConnectionAsync(
      { ...values, id: dataConnectionId },
      {
        onSuccess: () => {
          addSnackbar({ message: 'Data connection updated successfully', variant: 'success' });
          onClose();
        },
        onError: (error: unknown) => {
          addSnackbar({
            message: error instanceof Error ? error.message : 'Failed to update data connection',
            variant: 'danger',
          });
        },
      },
    );
  });

  if (isFetching) {
    return <Progress variant="page" />;
  }

  return (
    <Dialog open size="x-large" onClose={onClose}>
      <Form busy={isPending} onSubmit={onSubmit}>
        <Dialog.Header>
          <Dialog.Header.Title title="Update Connection Details" />
          <Dialog.Header.Description>Update connection details for a data source</Dialog.Header.Description>
        </Dialog.Header>
        <Dialog.Content>
          <FormProvider {...formMethods}>
            <DataConnectionForm snowflakeLinkedUser={snowflakeLinkedUser} />
          </FormProvider>
        </Dialog.Content>
        <Dialog.Actions>
          <Button type="submit" loading={isPending} round>
            Update
          </Button>
          <Button variant="secondary" round onClick={() => onClose()}>
            Cancel
          </Button>
        </Dialog.Actions>
      </Form>
    </Dialog>
  );
};
