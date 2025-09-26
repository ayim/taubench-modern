import React, { FC } from 'react';
import { Box, Button, Typography, Badge, Menu, Tooltip } from '@sema4ai/components';
import {
  IconChemicalBottle,
  IconPlay,
  IconDotsHorizontal,
  IconChevronDown,
  IconChevronUp,
  IconInformation,
  IconDownload,
  IconStatusCompleted,
  IconStatusError,
  IconStatusPending,
  IconStatusProcessing,
  IconTrash,
  IconCloseCircle,
  IconArrowRightCircle,
} from '@sema4ai/icons';
import { getRunStatus, hasTerminalTrials } from '../utils';
import { getPassFailCounts } from '../helpers/evalHelpers';
import type { Scenario, ScenarioRun } from '../types';

export interface ScenarioCardProps {
  scenario: Scenario;
  currentRun: ScenarioRun | null;
  isRunning: boolean;
  isAnyTestRunning: boolean;
  selectedTrials: number;
  expandedResults: boolean;
  onRunTest: (numTrials: number) => void;
  onToggleResults: () => void;
  onDownloadScenario: () => void;
  onDeleteScenario: () => void;
  onSetSelectedTrials: (numTrials: number) => void;
  onCancelTest: () => void;
  children?: React.ReactNode;
}

export const ScenarioCard: FC<ScenarioCardProps> = ({
  scenario,
  currentRun,
  isRunning,
  isAnyTestRunning,
  selectedTrials,
  expandedResults,
  onRunTest,
  onToggleResults,
  onDownloadScenario,
  onDeleteScenario,
  onSetSelectedTrials,
  onCancelTest,
  children,
}) => {
  const runStatus = isRunning ? 'EXECUTING' : (currentRun?.trials && getRunStatus(currentRun.trials));

  const renderStatusBadges = () => {    
    if (!currentRun) {
      return null;
    }
    
    if (isRunning) {
      return (
        <Badge
          icon={IconStatusProcessing}
          iconColor="yellow80"
          variant="yellow"
          label="Running"
        />
      );
    }
    
    const hasCompletedTrials = hasTerminalTrials(currentRun.trials ?? []);
    
    if (hasCompletedTrials) {
      const { passed, failed, canceled } = getPassFailCounts(currentRun.trials ?? []);
      
      return (
        <Box display="flex" alignItems="center" gap="$4">
          <Badge
            variant="secondary"
            icon={IconArrowRightCircle}
            forwardedAs="button"
            label="Results"
            iconVisible
            iconAfter={expandedResults ? IconChevronUp : IconChevronDown}
            onClick={onToggleResults}
          />
          {passed > 0 && (
            <Badge
              variant="green"
              icon={IconStatusCompleted}
              iconColor="green80"
              label={passed.toString()}
              size="small"
            />
          )}
          {failed > 0 && (
            <Badge
              variant="red"
              icon={IconStatusError}
              iconColor="red80"
              label={failed.toString()}
              size="small"
            />
          )}
          {canceled > 0 && (
            <Badge
              variant="yellow"
              icon={IconStatusPending}
              iconColor="yellow80"
              label={canceled.toString()}
              size="small"
            />
          )}
        </Box>
      );
    }
    
    return null;
  };

  return (
    <Box
      display="flex"
      flexDirection="column"
      gap="$8"
      mt="$16"
    >
      <Box display="flex" flexDirection="column" gap="$8">
        <Box>
          <Box 
            display="flex" 
            alignItems="center" 
            gap="$8" 
            flexDirection="row" 
            justifyContent='space-between'
          >
            <Box display="flex" alignItems="center" gap="$8">
              <IconChemicalBottle size={20} />
              <Typography variant="display-headline">{scenario.name}</Typography>
            </Box>
            
            <Menu
              trigger={
                <Button
                  variant="outline"
                  icon={IconDotsHorizontal}
                  round
                  aria-label="Scenario actions"
                  disabled={isAnyTestRunning}
                  size='small'
                />
              }
            >
              {selectedTrials === 4 ? (
                <Tooltip text='Run tests 1 time when clicking "Run Test"'>
                  <Menu.Item
                    onClick={() => onSetSelectedTrials(1)}
                    icon={IconInformation}
                  >
                    Switch to 1x
                  </Menu.Item>
                </Tooltip>
              ) : (
                <Tooltip text='Run tests 4 times when clicking "Run Test"'>
                  <Menu.Item
                    onClick={() => onSetSelectedTrials(4)}
                    icon={IconInformation}
                  >
                    Switch to 4x
                  </Menu.Item>
                </Tooltip>
              )}
              <Menu.Item 
                icon={IconDownload}
                onClick={onDownloadScenario}
              >
                Download JSON
              </Menu.Item>
              <Menu.Item 
                icon={IconTrash} 
                onClick={onDeleteScenario}
              >
                Delete
              </Menu.Item>
            </Menu>
          </Box>
          
          <Typography variant="body-small" mt="$8">
            {scenario.description}
          </Typography>
        </Box>
        
        <Box width="100%" display="flex" alignItems="center" gap="$8">
          {isRunning ? (
            <Button
              variant="outline"
              round
              icon={IconCloseCircle}
              onClick={onCancelTest}
            >
              Cancel
            </Button>
          ) : (
            <Button
              variant="outline"
              round
              disabled={isAnyTestRunning}
              icon={IconPlay}
              onClick={() => onRunTest(selectedTrials)}
            >
              {selectedTrials === 1 ? 'Run Test' : `Run Test (${selectedTrials}x)`}
            </Button>
          )}
          
          {runStatus && (
            <Box display="flex" alignItems="center" gap="$4">
              {renderStatusBadges()}
            </Box>
          )}
        </Box>
      </Box>

      {children}
    </Box>
  );
};
