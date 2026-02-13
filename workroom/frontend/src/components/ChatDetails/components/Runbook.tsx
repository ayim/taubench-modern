import { useEffect, useState } from 'react';
import { Box, Button, Progress, Typography } from '@sema4ai/components';
import { IconShare } from '@sema4ai/icons';
import { useParams } from '@tanstack/react-router';

import { useAgentDetailsQuery } from '~/queries/agents';
import { RunbookDialog } from '~/components/RunbookEditor';
import { useUserRole, UserRole } from '~/hooks/useUserRole';
import { useAgentDetailsContext } from './context';

export const Runbook = () => {
  const { agentId = '' } = useParams({ strict: false });
  const [isRunbookDialogOpen, setIsRunbookDialogOpen] = useState(false);
  const hasAdminRole = useUserRole(UserRole.Admin);
  const { updateAgent } = useAgentDetailsContext();
  const { data, isLoading } = useAgentDetailsQuery({ agentId });
  const [runbook, setRunbook] = useState<string | undefined>('');

  useEffect(() => {
    if (data?.runbook) {
      setRunbook(data.runbook);
    }
  }, [data]);

  const onOpenRunbookDialog = () => {
    setIsRunbookDialogOpen(true);
  };

  const onCloseRunbookDialog = async (value?: string) => {
    setIsRunbookDialogOpen(false);

    if (value && value !== runbook) {
      setRunbook(value);
      updateAgent({ runbook: value });
    }
  };

  if (isLoading && isRunbookDialogOpen) {
    return <Progress variant="page" />;
  }

  return (
    <Box display="flex" flexDirection="column" gap="$8">
      <Typography fontWeight="medium">Runbook</Typography>
      <Box>
        <Button disabled={isLoading} iconAfter={IconShare} variant="outline" onClick={onOpenRunbookDialog} round>
          {hasAdminRole ? 'Edit Runbook' : 'View Runbook'}
        </Button>
      </Box>
      {isRunbookDialogOpen && runbook && (
        <RunbookDialog readOnly={!hasAdminRole} onClose={onCloseRunbookDialog} value={runbook} />
      )}
    </Box>
  );
};
