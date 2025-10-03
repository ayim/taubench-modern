import { FC, FormEvent, useState } from 'react';
import { Button, Dialog, Form, Input, Box } from '@sema4ai/components';

type Props = {
  onClose: () => void;
  onRename: (name: string) => void;
  entityName: string;
  entityType: string;
};

export const RenameDialog: FC<Props> = ({ onClose, entityName, onRename, entityType }) => {
  const [name, setName] = useState(entityName);

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

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
    <Dialog onClose={onClose} open>
      <Form onSubmit={onSubmit}>
        <Dialog.Header>
          <Dialog.Header.Title title={`Rename ${entityType}`} />
          <Dialog.Header.Description>Give your {entityType} and clear name.</Dialog.Header.Description>
        </Dialog.Header>
        <Dialog.Content>
          <Box py={1}>
            <Input autoFocus aria-label={`${entityType} name`} value={name} onChange={(e) => setName(e.target.value)} />
          </Box>
        </Dialog.Content>
        <Dialog.Actions>
          <Button variant="primary" type="submit" round>
            Rename
          </Button>
          <Button variant="secondary" onClick={onClose} round>
            Cancel
          </Button>
        </Dialog.Actions>
      </Form>
    </Dialog>
  );
};
