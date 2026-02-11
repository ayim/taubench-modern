import { FC, ReactNode } from 'react';
import { Box, Button, Dialog, Typography } from '@sema4ai/components';
import { IconArrowLeft } from '@sema4ai/icons';

export type InlineEditorProps = {
  breadcrumb: string;
  title: string;
  saveLabel: string;
  isSaveDisabled: boolean;
  isSaving?: boolean;
  isEditing: boolean;
  onSave: () => void | Promise<void>;
  onDelete: () => void;
  onBack: () => void;
  contentMaxWidth?: number;
  children: ReactNode;
};

export const InlineEditor: FC<InlineEditorProps> = ({
  breadcrumb,
  title,
  saveLabel,
  isSaveDisabled,
  isSaving,
  isEditing,
  onSave,
  onDelete,
  onBack,
  contentMaxWidth,
  children,
}) => {
  return (
    <>
      <Dialog.Content maxWidth={contentMaxWidth}>
        <Box display="flex" flexDirection="column" gap="$16" height="100%">
          <Box display="flex" alignItems="center" gap="$8">
            <Button variant="ghost-subtle" size="small" icon={IconArrowLeft} aria-label="Back" onClick={onBack} />
            <Typography variant="body-small" color="content.subtle">
              {breadcrumb}
            </Typography>
            <Typography variant="body-small" color="content.subtle">
              /
            </Typography>
            <Typography variant="body-small">{title}</Typography>
          </Box>

          <Typography variant="display-medium">{title}</Typography>

          {children}
        </Box>
      </Dialog.Content>

      <Dialog.Actions>
        <Button variant="primary" onClick={onSave} disabled={isSaveDisabled} loading={isSaving} round>
          {saveLabel}
        </Button>
        <Button variant="secondary" onClick={onBack} round>
          Cancel
        </Button>
        {isEditing && (
          <Button variant="destructive" onClick={onDelete} align="secondary" round>
            Delete
          </Button>
        )}
      </Dialog.Actions>
    </>
  );
};
