import { FC, useRef, ChangeEventHandler } from 'react';
import { Box, Progress, Dialog, Button } from '@sema4ai/components';
import { useThreadMessagesQuery } from '../../../../queries';
import { useParams } from '../../../../hooks';
import { CreateEvalDialog } from './components/CreateEvalDialog';
import { useEvalSidebar } from './hooks/useEvalSidebar';
import { EvalHeader, EvalEmptyState, ScenarioCard, ScenarioResults, UserFacingMetrics } from './components';

export interface EvalSidebarViewProps {
  agentId: string;
}

export const EvalSidebarView: FC<EvalSidebarViewProps> = ({ agentId }) => {
  const { threadId } = useParams('/thread/$agentId/$threadId');
  const { data: messages = [] } = useThreadMessagesQuery({ threadId });

  const sidebar = useEvalSidebar({
    agentId,
    threadId,
  });

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange: ChangeEventHandler<HTMLInputElement> = (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    sidebar.handleImportScenarios(file);
    // eslint-disable-next-line no-param-reassign
    event.target.value = '';
  };

  const hasMessages = messages.length >= 2;

  if (sidebar.loading) {
    return (
      <Box display="flex" flexDirection="column" gap="$16" padding="$16" height="100%">
        <Box display="flex" alignItems="center" justifyContent="center" flex="1">
          <Progress />
        </Box>
      </Box>
    );
  }

  if (sidebar.evaluations.length === 0) {
    return (
      <Box display="flex" height="100%" alignItems="center" justifyContent="center">
        <EvalEmptyState
          hasMessages={hasMessages}
          onAddEvaluation={sidebar.handleAddEvaluation}
          onImportScenarios={handleImportClick}
          isFetchingSuggestion={sidebar.isFetchingSuggestion}
          isImporting={sidebar.importScenariosMutation.isPending}
        />

        <input
          ref={fileInputRef}
          type="file"
          accept=".zip,application/zip"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />

        {sidebar.deleteTarget && (
          <Dialog open onClose={() => sidebar.setDeleteTarget(null)}>
            <Dialog.Header>
              <Dialog.Header.Title title="Delete Evaluation" />
            </Dialog.Header>
            <Dialog.Content>
              Are you sure you want to delete &quot;{sidebar.deleteTarget.name}&quot;? This action cannot be undone.
            </Dialog.Content>
            <Dialog.Actions>
              <Button
                loading={sidebar.deleteScenarioMutation.isPending}
                onClick={() => sidebar.handleDeleteConfirm(sidebar.deleteTarget)}
              >
                Delete
              </Button>
              <Button variant="secondary" onClick={() => sidebar.setDeleteTarget(null)}>
                Cancel
              </Button>
            </Dialog.Actions>
          </Dialog>
        )}

        <CreateEvalDialog
          open={sidebar.createDialogOpen}
          onClose={sidebar.resetCreateDialogState}
          onSubmit={sidebar.handleSubmitEvaluation}
          isLoading={sidebar.isSubmittingEvaluation}
          initialValues={sidebar.suggestedValues}
          mode={sidebar.editingScenario ? 'edit' : 'create'}
        />
      </Box>
    );
  }

  return (
    <>
      <Box display="flex" flexDirection="column" gap="$16" padding="$16" height="100%" overflow="hidden">
        <EvalHeader
          hasMessages={hasMessages}
          hasEvaluations={sidebar.evaluations.length > 0}
          onAddEvaluation={sidebar.handleAddEvaluation}
          onExportScenarios={sidebar.handleExportScenarios}
          isExporting={sidebar.exportScenariosMutation.isPending}
          isFetchingSuggestion={sidebar.isFetchingSuggestion}
          onImportScenarios={handleImportClick}
          isImporting={sidebar.importScenariosMutation.isPending}
        />

        <UserFacingMetrics
          batchSummary={sidebar.lastBatchSummary}
          showRunbookWarning={sidebar.hasRunbookUpdated && !sidebar.runbookWarningDismissed}
          onDismissRunbookWarning={() => sidebar.setRunbookWarningDismissed(true)}
          onRunAllTests={sidebar.handleRunAll}
          selectedTrialsForAll={sidebar.selectedTrialsForAll}
          onSetSelectedTrialsForAll={sidebar.setSelectedTrialsForAll}
          isAnyTestRunning={sidebar.isAnyTestRunning}
          isBatchRunning={sidebar.isBatchRunning}
          isCancelingAll={sidebar.isCancelingAll}
          onCancelAllTests={sidebar.handleCancelAllRunning}
          hasEvaluations={sidebar.evaluations.length > 0}
        />

        <Box display="flex" flexDirection="column" gap="$12" flex="1" overflow="auto" minHeight="0">
          {sidebar.evaluations.map(({ scenario, allRuns, currentRun, isRunning }) => {
            const selectedRunIndex = sidebar.selectedRunIndices.get(scenario.scenario_id) ?? 0;
            const selectedTrials = sidebar.getSelectedTrialsForScenario(scenario.scenario_id);
            const expandedResults = sidebar.expandedResults.has(scenario.scenario_id);

            return (
              <ScenarioCard
                key={scenario.scenario_id}
                scenario={scenario}
                currentRun={currentRun}
                isRunning={isRunning}
                isAnyTestRunning={sidebar.isAnyTestRunning}
                selectedTrials={selectedTrials}
                expandedResults={expandedResults}
                onRunTest={(numTrials) => sidebar.handleRunTest(scenario, numTrials)}
                onToggleResults={() => sidebar.toggleResults(scenario.scenario_id)}
                onDeleteScenario={() =>
                  sidebar.setDeleteTarget({
                    scenario_id: scenario.scenario_id,
                    name: scenario.name,
                  })
                }
                onEditScenario={() => sidebar.handleEditEvaluation(scenario)}
                onSetSelectedTrials={(numTrials) =>
                  sidebar.setSelectedTrials((prev) => new Map(prev).set(scenario.scenario_id, numTrials))
                }
                onCancelTest={sidebar.handleCancelTest(scenario, currentRun)}
              >
                {expandedResults && (
                  <ScenarioResults
                    scenarioId={scenario.scenario_id}
                    scenarioRunId={currentRun?.scenario_run_id}
                    configuration={currentRun?.configuration}
                    trials={currentRun?.trials || []}
                    selectedRunIndex={selectedRunIndex}
                    totalRuns={allRuns.length}
                    allRuns={allRuns}
                    isRunning={isRunning}
                    expandedTrials={sidebar.expandedTrials}
                    expandedEvaluations={sidebar.expandedEvaluations}
                    onPreviousRun={() => sidebar.handlePreviousRun(scenario.scenario_id)}
                    onNextRun={() => sidebar.handleNextRun(scenario.scenario_id, allRuns.length)}
                    onSelectRun={(runIndex) => sidebar.handleSelectRun(scenario.scenario_id, runIndex)}
                    onToggleTrialDetails={sidebar.toggleTrialDetails}
                    onToggleEvaluationDetails={sidebar.toggleEvaluationDetails}
                    onViewResults={sidebar.handleViewResults}
                  />
                )}
              </ScenarioCard>
            );
          })}
        </Box>
      </Box>

      {sidebar.deleteTarget && (
        <Dialog open onClose={() => sidebar.setDeleteTarget(null)}>
          <Dialog.Header>
            <Dialog.Header.Title title="Delete Evaluation" />
          </Dialog.Header>
          <Dialog.Content>
            Are you sure you want to delete &quot;{sidebar.deleteTarget.name}&quot;? This action cannot be undone.
          </Dialog.Content>
          <Dialog.Actions>
            <Button
              loading={sidebar.deleteScenarioMutation.isPending}
              onClick={() => sidebar.handleDeleteConfirm(sidebar.deleteTarget)}
            >
              Delete
            </Button>
            <Button variant="secondary" onClick={() => sidebar.setDeleteTarget(null)}>
              Cancel
            </Button>
          </Dialog.Actions>
        </Dialog>
      )}

      <CreateEvalDialog
        open={sidebar.createDialogOpen}
        onClose={sidebar.resetCreateDialogState}
        onSubmit={sidebar.handleSubmitEvaluation}
        isLoading={sidebar.isSubmittingEvaluation}
        initialValues={sidebar.suggestedValues}
        mode={sidebar.editingScenario ? 'edit' : 'create'}
      />

      <input
        ref={fileInputRef}
        type="file"
        accept=".zip,application/zip"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
    </>
  );
};
