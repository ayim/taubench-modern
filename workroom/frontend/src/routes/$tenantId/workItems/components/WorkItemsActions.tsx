import { Box, Button } from '@sema4ai/components';
import { IconRefresh } from '@sema4ai/icons';
import React from 'react';

export interface WorkItemsActionsProps {
  selectedRows: string[];
  handleRestartClick: () => void;
  handleSyncClick: () => Promise<void>;
  hasStaleData: boolean;
  isRestarting?: boolean;
  isSyncing?: boolean;
}

const WorkItemsActions: React.FC<WorkItemsActionsProps> = ({
  selectedRows,
  handleRestartClick,
  handleSyncClick,
  hasStaleData,
  isRestarting = false,
  isSyncing = false,
}) => {
  return (
    <Box className="flex justify-end flex-row gap-2">
      <Button
        data-testid="sync-button"
        iconAfter={IconRefresh}
        onClick={handleSyncClick}
        title="Sync"
        round
        aria-label="Sync"
        variant="primary"
        className="border border-solid border-[#DADEE3] !bg-white"
        disabled={!hasStaleData || isSyncing}
        loading={isSyncing}
      >
        {isSyncing ? 'Syncing...' : 'Sync'}
      </Button>

      <Button
        data-testid="reprocess-button"
        aria-label="button"
        type="button"
        disabled={selectedRows.length === 0 || isRestarting}
        loading={isRestarting}
        variant="ghost"
        className="border border-solid border-[#DADEE3] !bg-white"
        onClick={handleRestartClick}
        round
      >
        {isRestarting ? 'Restarting...' : 'Restart'}
      </Button>
    </Box>
  );
};

export default WorkItemsActions;
