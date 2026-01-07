import { zodResolver } from '@hookform/resolvers/zod';
import { Box, Button, Dialog, Form, Input, useSnackbar } from '@sema4ai/components';
import { useNavigate } from '@tanstack/react-router';
import type { FC } from 'react';
import { useCallback } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { trpc } from '~/lib/trpc';
import { formatDatetime } from '~/lib/utils';
import { ApiKeyDisplay } from './ApiKeyDisplay';

const updateApiKeySchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(100, 'Name must be at most 100 characters'),
});

type UpdateApiKeyFormValues = z.infer<typeof updateApiKeySchema>;

type ApiKeyDetails = {
  id: string;
  name: string;
  createdAt: string;
  lastUsedAt: string | null;
};

type Props = {
  apiKey: ApiKeyDetails;
  tenantId: string;
};

export const EditApiKeyDialog: FC<Props> = ({ apiKey, tenantId }) => {
  const navigate = useNavigate();
  const { addSnackbar } = useSnackbar();

  const trpcUtils = trpc.useUtils();

  const handleClose = useCallback(() => {
    navigate({ to: '/tenants/$tenantId/configuration/api-keys', params: { tenantId } });
  }, [navigate, tenantId]);

  const updateMutation = trpc.apiKeys.update.useMutation();

  const form = useForm<UpdateApiKeyFormValues>({
    resolver: zodResolver(updateApiKeySchema),
    defaultValues: {
      name: apiKey.name,
    },
    mode: 'onChange',
  });

  const handleSubmit = form.handleSubmit((values) => {
    updateMutation.mutate(
      { id: apiKey.id, name: values.name },
      {
        onSuccess: () => {
          trpcUtils.apiKeys.list.invalidate();
          trpcUtils.apiKeys.get.invalidate({ id: apiKey.id });
          addSnackbar({ message: 'API key updated', variant: 'success' });
          handleClose();
        },
        onError: (error) => addSnackbar({ message: error.message, variant: 'danger' }),
      },
    );
  });

  return (
    <Dialog open size="x-large" onClose={handleClose}>
      <Form onSubmit={handleSubmit} busy={updateMutation.isPending}>
        <Dialog.Header>
          <Dialog.Header.Title title="Edit API Key" />
        </Dialog.Header>
        <Dialog.Content>
          <Box display="flex" flexDirection="column" gap="$16">
            <Input label="Name" {...form.register('name')} error={form.formState.errors.name?.message} />
            <Box display="flex" gap="$24">
              <Box display="flex" flexDirection="column" gap="$4">
                <Box as="label" fontWeight="medium" color="content.subtle">
                  Created
                </Box>
                <Box>{formatDatetime(apiKey.createdAt)}</Box>
              </Box>

              <Box display="flex" flexDirection="column" gap="$4">
                <Box as="label" fontWeight="medium" color="content.subtle">
                  Last Used
                </Box>
                <Box>{apiKey.lastUsedAt ? formatDatetime(apiKey.lastUsedAt) : 'Never'}</Box>
              </Box>
            </Box>
            <ApiKeyDisplay apiKey={{ id: apiKey.id, decryptedValue: null }} tenantId={tenantId} />
          </Box>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="primary" round type="submit" loading={updateMutation.isPending}>
            Save
          </Button>
          <Button variant="secondary" round type="button" onClick={handleClose} disabled={updateMutation.isPending}>
            Cancel
          </Button>
        </Dialog.Actions>
      </Form>
    </Dialog>
  );
};
