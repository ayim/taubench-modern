import { FC } from 'react';
import { Button, Dialog, Form, Input, Box } from '@sema4ai/components';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const renameFormSchema = z.object({
  name: z.string().trim().min(1, 'Name cannot be empty'),
});

type RenameFormData = z.infer<typeof renameFormSchema>;

type Props = {
  onClose: () => void;
  onRename: (name: string) => void;
  entityName: string;
  entityType: string;
  actionType?: 'Rename' | 'Update';
  actionDescription?: string;
  multiLine?: boolean;
};

export const RenameDialog: FC<Props> = ({
  actionType = 'Rename',
  actionDescription,
  onClose,
  entityName,
  onRename,
  entityType,
  multiLine = false,
}) => {
  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
  } = useForm<RenameFormData>({
    resolver: zodResolver(renameFormSchema),
    defaultValues: {
      name: entityName,
    },
    mode: 'onChange',
  });

  const { ref, ...registerProps } = register('name');

  const onSubmit = handleSubmit((data) => {
    const newName = data.name.trim();

    if (entityName === newName) {
      onClose();
      return;
    }

    onClose();
    onRename(newName);
  });

  return (
    <Dialog onClose={onClose} width={multiLine ? 720 : undefined} open>
      <Form onSubmit={onSubmit}>
        <Dialog.Header>
          <Dialog.Header.Title title={`${actionType} ${entityType}`} />
          <Dialog.Header.Description>
            {actionDescription || `Give your ${entityType} a clear name.`}
          </Dialog.Header.Description>
        </Dialog.Header>
        <Dialog.Content>
          <Box py={1}>
            <Input
              rows={multiLine ? 8 : undefined}
              autoFocus
              aria-label={`${entityType} name`}
              error={errors.name?.message}
              {...registerProps}
              ref={(element) => {
                ref(element);
                if (element) {
                  requestAnimationFrame(() => element.select());
                }
              }}
            />
          </Box>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="primary" type="submit" disabled={!isValid} round>
            {actionType}
          </Button>
          <Button variant="secondary" onClick={onClose} round>
            Cancel
          </Button>
        </Dialog.Actions>
      </Form>
    </Dialog>
  );
};
