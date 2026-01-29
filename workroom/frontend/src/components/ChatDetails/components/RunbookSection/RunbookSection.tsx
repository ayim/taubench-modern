import { Box, Button, Typography } from '@sema4ai/components';
import { IconShare } from '@sema4ai/icons';
import { memo } from 'react';
import { RunbookDialog } from './RunbookEditor/RunbookDialog';
import { useToggle } from '../../../../hooks';

type RunbookSectionProps = {
  agentName: string;
  runbookMarkdown: string;
};

export const RunbookSection = memo<RunbookSectionProps>(({ agentName, runbookMarkdown }) => {
  const { val: isDislogOpen, setTrue: openDialog, setFalse: closeDialog } = useToggle();

  return (
    <Box display="flex" flexDirection="column" gap="$10">
      <Typography variant="body-medium" fontWeight="bold">
        Runbook
      </Typography>
      <Box>
        <Button iconAfter={IconShare} round onClick={openDialog} variant="outline" width="fit-content">
          View Runbook
        </Button>
      </Box>
      <RunbookDialog
        open={isDislogOpen}
        onClose={closeDialog}
        agentName={agentName}
        runbookMarkdown={runbookMarkdown}
      />
    </Box>
  );
});
