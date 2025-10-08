import { FC, FormEvent, useState } from 'react';
import { Button, Dialog, Form, Input, Box } from '@sema4ai/components';

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
  const [name, setName] = useState(entityName);

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    e.stopPropagation();

    const newName = name.trim();

    if (entityName === newName) {
      onClose();
      return;
    }

    if (newName.length === 0) {
      return;
    }

    onClose();
    onRename(newName);
  };

  return (
    <Dialog onClose={onClose} width={multiLine ? 720 : undefined} open>
      <Form onSubmit={onSubmit}>
        <Dialog.Header>
          <Dialog.Header.Title title={`${actionType} ${entityType}`} />
          <Dialog.Header.Description>
            {actionDescription || `Give your ${entityType} and clear name.`}
          </Dialog.Header.Description>
        </Dialog.Header>
        <Dialog.Content>
          <Box py={1}>
            <Input
              rows={multiLine ? 8 : undefined}
              autoFocus
              aria-label={`${entityType} name`}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Box>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="primary" type="submit" round>
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
