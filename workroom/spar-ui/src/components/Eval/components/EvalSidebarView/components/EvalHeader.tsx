import { FC } from 'react';
import { Box, Button, Typography, Tooltip, Menu } from '@sema4ai/components';
import {
  IconInformation,
  IconPlus,
  IconLightBulb,
  IconDownload,
  IconUpload,
  IconDotsHorizontal,
  IconTrash,
} from '@sema4ai/icons';

export interface EvalHeaderProps {
  hasMessages: boolean;
  hasEvaluations: boolean;
  onAddEvaluation: () => void;
  isFetchingSuggestion: boolean;
  onExportScenarios: () => void;
  isExporting: boolean;
  onImportScenarios: () => void;
  isImporting: boolean;
  onDeleteAllScenarios: () => void;
  isDeletingAll: boolean;
}

export const EvalHeader: FC<EvalHeaderProps> = ({
  hasMessages,
  hasEvaluations,
  onAddEvaluation,
  isFetchingSuggestion,
  onExportScenarios,
  isExporting,
  onImportScenarios,
  isImporting,
  onDeleteAllScenarios,
  isDeletingAll,
}) => {
  const evaluationActionsMenu = (
    <Menu
      trigger={
        <Button variant="outline" round size="small" icon={IconDotsHorizontal} aria-label="Evaluation actions" />
      }
    >
      <Menu.Item icon={IconDownload} onClick={onImportScenarios} disabled={isImporting}>
        {isImporting ? 'Importing...' : 'Import Evaluations'}
      </Menu.Item>
      <Menu.Item icon={IconUpload} onClick={onExportScenarios} disabled={!hasEvaluations || isExporting}>
        {isExporting ? 'Exporting...' : 'Export Evaluations'}
      </Menu.Item>
      <Menu.Item icon={IconTrash} onClick={onDeleteAllScenarios} disabled={!hasEvaluations || isDeletingAll}>
        {isDeletingAll ? 'Deleting...' : 'Delete All Evaluations'}
      </Menu.Item>
    </Menu>
  );

  return (
    <Box display="flex" flexDirection="column" gap="$8" flexShrink="0">
      <Box display="flex" alignItems="center" gap="$8">
        <Typography variant="display-small">Evaluations</Typography>
        <Tooltip text="Evaluations are used to test the performance of your agent.">
          <IconInformation size="48" color="content.subtle.light" />
        </Tooltip>
      </Box>

      <Typography variant="body-medium">All evaluation runs will be shown here.</Typography>

      <Box
        display="flex"
        justifyContent={hasMessages ? 'flex-start' : 'space-between'}
        alignItems="center"
        paddingTop="$8"
        mb="$8"
        gap="$12"
        flexWrap="wrap"
      >
        {!hasMessages && (
          <Box
            backgroundColor="background.notification.light"
            padding="$20"
            borderRadius="$12"
            display="flex"
            alignItems="center"
            gap="$8"
          >
            <IconLightBulb size={24} />
            <Typography variant="body-medium">Talk to your agent to be able to add an evaluation.</Typography>
          </Box>
        )}

        <Box display="flex" alignItems="center" gap="$8">
          <Button
            variant="outline"
            round
            onClick={onAddEvaluation}
            loading={isFetchingSuggestion}
            disabled={!hasMessages || isFetchingSuggestion}
          >
            {!isFetchingSuggestion && (
              <>
                <IconPlus size="16" />
                Add Evaluation
              </>
            )}
            {isFetchingSuggestion && 'Generating Evaluation...'}
          </Button>
          {evaluationActionsMenu}
        </Box>
      </Box>
    </Box>
  );
};
