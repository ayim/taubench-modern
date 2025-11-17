import { FC } from 'react';
import { Box, Chat, Dialog, Typography } from '@sema4ai/components';

import { markdownRules } from '../Chat/components/markdown';

interface AssemblyInfoDialogProps {
  open: boolean;
  onClose: () => void;
  dataFrameName: string;
  assemblyInfo: string;
}

export const AssemblyInfoDialog: FC<AssemblyInfoDialogProps> = ({ open, onClose, dataFrameName, assemblyInfo }) => {
  return (
    <Dialog open={open} onClose={onClose} size="x-large">
      <Dialog.Header>
        <Typography fontSize="$20" fontWeight="bold">
          Assembly Info: {dataFrameName}
        </Typography>
      </Dialog.Header>
      <Dialog.Content>
        <Box
          display="flex"
          flexDirection="column"
          padding="$16"
          style={{
            maxHeight: '70vh',
            overflow: 'auto',
          }}
        >
          <Chat.Markdown parserRules={markdownRules} messageId="" streaming={false}>
            {assemblyInfo}
          </Chat.Markdown>
        </Box>
      </Dialog.Content>
    </Dialog>
  );
};
