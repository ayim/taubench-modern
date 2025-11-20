import { FC, useCallback, useRef } from 'react';
import { Button, Dialog, Form, Input, Box, useForkRef } from '@sema4ai/components';
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
  const localRef = useRef<HTMLInputElement>(null);

  const selectInput = useCallback((ref: HTMLInputElement) => {
    if (localRef.current) {
      return;
    }
    localRef.current = ref;
    ref.select();
  }, []);

  const { ref: nameRef, ...registerProps } = register('name');
  const inputRef = useForkRef<HTMLInputElement>(nameRef, selectInput);

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    e.stopPropagation();

    handleSubmit((data) => {
      const newName = data.name.trim();

      if (entityName === newName) {
        onClose();
        return;
      }

      onClose();
      onRename(newName);
    })();
  };

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
              ref={inputRef}
              {...registerProps}
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
