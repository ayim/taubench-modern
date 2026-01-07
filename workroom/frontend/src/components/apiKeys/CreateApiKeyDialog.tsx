import { zodResolver } from '@hookform/resolvers/zod';
import { Button, Dialog, Form, Input, useSnackbar } from '@sema4ai/components';
import { useNavigate } from '@tanstack/react-router';
import { type FC, useCallback, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { trpc } from '~/lib/trpc';
import { ApiKeyDisplay } from './ApiKeyDisplay';

const createApiKeySchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(100, 'Name must be at most 100 characters'),
});

type CreateApiKeyFormValues = z.infer<typeof createApiKeySchema>;

type CreatedApiKey = {
  id: string;
  name: string;
  value: string;
};

type Props = {
  tenantId: string;
};

export const CreateApiKeyDialog: FC<Props> = ({ tenantId }) => {
  const navigate = useNavigate();
  const { addSnackbar } = useSnackbar();
  const [createdApiKey, setCreatedApiKey] = useState<CreatedApiKey | null>(null);

  const trpcUtils = trpc.useUtils();
  const createMutation = trpc.apiKeys.create.useMutation();

  const handleClose = useCallback(() => {
    navigate({ to: '/tenants/$tenantId/configuration/api-keys', params: { tenantId } });
  }, [navigate, tenantId]);

  const form = useForm<CreateApiKeyFormValues>({
    resolver: zodResolver(createApiKeySchema),
    defaultValues: {
      name: '',
    },
    mode: 'onChange',
  });

  const handleSubmit = form.handleSubmit((values) => {
    createMutation.mutate(
      { name: values.name },
      {
        onSuccess: (createdResult) => {
          trpcUtils.apiKeys.list.invalidate();
          setCreatedApiKey(createdResult);
        },
        onError: (error) => addSnackbar({ message: error.message, variant: 'danger' }),
      },
    );
  });

  const dialogContent = (() => {
    if (createdApiKey) {
      return (
        <>
          <Dialog.Header>
            <Dialog.Header.Title title="Save Your Key" />
            <Dialog.Header.Description>
              Keep the secret secure, as anyone with access to your API key can make requests on your behalf.
            </Dialog.Header.Description>
          </Dialog.Header>
          <Dialog.Content>
            <ApiKeyDisplay apiKey={{ id: createdApiKey.id, decryptedValue: createdApiKey.value }} tenantId={tenantId} />
          </Dialog.Content>
          <Dialog.Actions>
            <Button variant="secondary" round onClick={handleClose}>
              Close
            </Button>
          </Dialog.Actions>
        </>
      );
    }

    return (
      <Form onSubmit={handleSubmit} busy={createMutation.isPending}>
        <Dialog.Header>
          <Dialog.Header.Title title="Create API Key" />
          <Dialog.Header.Description>
            Create a new API key to authenticate requests to the public API.
          </Dialog.Header.Description>
        </Dialog.Header>
        <Dialog.Content>
          <Form.Fieldset>
            <Input
              label="Name"
              {...form.register('name')}
              error={form.formState.errors.name?.message}
              placeholder="My API Key"
              autoFocus
            />
          </Form.Fieldset>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="primary" type="submit" round loading={createMutation.isPending}>
            Create
          </Button>
          <Button variant="secondary" type="button" round onClick={handleClose} disabled={createMutation.isPending}>
            Cancel
          </Button>
        </Dialog.Actions>
      </Form>
    );
  })();

  return (
    <Dialog open size="x-large" onClose={handleClose}>
      {dialogContent}
    </Dialog>
  );
};
