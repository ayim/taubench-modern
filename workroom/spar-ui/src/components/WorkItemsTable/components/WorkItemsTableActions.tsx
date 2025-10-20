import { Box, Button, Typography } from '@sema4ai/components';
import { IconDownloadCloud, IconRefresh, IconSeparator } from '@sema4ai/icons';
import { FC } from 'react';

export type TableActionsProps = {
  selectionCount: number;
  onResetSelection: () => void;
  onReprocess?: () => void;
  onDownloadRaw?: () => void;
};

export const WorkItemsTableActions: FC<TableActionsProps> = ({
  selectionCount,
  onResetSelection,
  onReprocess,
  onDownloadRaw,
}) => {
  return (
    <Box display="flex" gap="$4" alignItems="center" px="$20" py="$8">
      <Button.Group collapse maxWidth="max-content">
        {onDownloadRaw && (
          <Button round icon={IconDownloadCloud} onClick={onDownloadRaw}>
            Download JSON
          </Button>
        )}
        {onReprocess && (
          <Button round icon={IconRefresh} variant="secondary" onClick={onReprocess}>
            Reprocess
          </Button>
        )}
        <Button round variant="ghost" onClick={onResetSelection}>
          Reset Selection
        </Button>
      </Button.Group>
      <IconSeparator color="border.primary" />
      <Typography pl="$12" color="content.subtle" variant="body-medium">
        {selectionCount} selected
      </Typography>
    </Box>
  );
};

