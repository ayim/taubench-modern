import { FC } from 'react';
import { Button, Dialog, Form, useSnackbar } from '@sema4ai/components';
import { DataConnection } from '@sema4ai/data-interface';
import { zodResolver } from '@hookform/resolvers/zod';
import { FormProvider, useForm, Resolver } from 'react-hook-form';

import { useCreateDataConnectionMutation } from '../../../../queries';
import { DataConnectionForm } from './DataConnectionForm';

type Props = {
  onClose: () => void;
};

export const CreateDataConnection: FC<Props> = ({ onClose }) => {
  const { addSnackbar } = useSnackbar();
  const { mutateAsync: createDataConnectionAsync, isPending } = useCreateDataConnectionMutation({});

  const formMethods = useForm<DataConnection>({
    resolver: zodResolver(DataConnection) as Resolver<DataConnection>,
    defaultValues: {
      engine: 'postgres',
    },
  });

  const onSubmit = formMethods.handleSubmit(async (values) => {
    createDataConnectionAsync(values, {
      onSuccess: () => {
        addSnackbar({ message: 'Data connection created successfully', variant: 'success' });
        onClose();
      },
      onError: (error: unknown) => {
        addSnackbar({
          message: error instanceof Error ? error.message : 'Failed to create data connection',
          variant: 'danger',
        });
      },
    });
  });

  return (
    <Dialog open size="x-large" onClose={onClose}>
      <Form busy={isPending} onSubmit={onSubmit}>
        <Dialog.Header>
          <Dialog.Header.Title title="New Connection Details" />
          <Dialog.Header.Description>Create connection details for a data source</Dialog.Header.Description>
        </Dialog.Header>
        <Dialog.Content>
          <FormProvider {...formMethods}>
            <DataConnectionForm allowEngineChange />
          </FormProvider>
        </Dialog.Content>
        <Dialog.Actions>
          <Button type="submit" loading={isPending} round>
            Create
          </Button>
          <Button variant="secondary" round onClick={() => onClose()}>
            Cancel
          </Button>
        </Dialog.Actions>
      </Form>
    </Dialog>
  );
};
