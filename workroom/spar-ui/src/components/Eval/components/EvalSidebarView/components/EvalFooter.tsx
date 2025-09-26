import { FC } from 'react';
import { Box, Button, Menu } from '@sema4ai/components';
import { IconSendSmall, IconDotsHorizontal } from '@sema4ai/icons';

export interface EvalFooterProps {
  hasEvaluations: boolean;
  isAnyTestRunning: boolean;
  selectedTrialsForAll: number;
  onRunAll: (numTrials: number) => void;
  onSetSelectedTrialsForAll: (numTrials: number) => void;
}

export const EvalFooter: FC<EvalFooterProps> = ({
  hasEvaluations,
  isAnyTestRunning,
  selectedTrialsForAll,
  onRunAll,
  onSetSelectedTrialsForAll,
}) => {
  if (!hasEvaluations) {
    return null;
  }

  return (
    <Box 
      display="flex" 
      justifyContent="flex-end" 
      alignItems="center" 
      flexShrink="0" 
      paddingTop="$8" 
      gap="$4"
    >
      <Button 
        icon={IconSendSmall}
        variant="primary" 
        disabled={isAnyTestRunning}
        onClick={() => onRunAll(selectedTrialsForAll)}
      >
        {selectedTrialsForAll === 1 ? 'Run All Tests' : `Run All Tests (${selectedTrialsForAll}x)`}
      </Button>
      
      <Menu
        trigger={
          <Button 
            variant="outline"
            icon={IconDotsHorizontal}
            round
            disabled={isAnyTestRunning}
            aria-label="Run all tests options"
          />
        }
      >
        {selectedTrialsForAll === 4 ? (
          <Menu.Item onClick={() => onSetSelectedTrialsForAll(1)}>
            Switch to single run
          </Menu.Item>
        ) : (
          <Menu.Item onClick={() => onSetSelectedTrialsForAll(4)}>
            Switch to 4x runs
          </Menu.Item>
        )}
      </Menu>
    </Box>
  );
};
