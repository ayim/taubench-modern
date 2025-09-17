import { createFileRoute, useRouteContext, useNavigate } from '@tanstack/react-router';
import { useState, useMemo } from 'react';
import { useQueries } from '@tanstack/react-query';
import { Dialog, Button, useSnackbar } from '@sema4ai/components';
import { EvalSidebarView, CreateEvalDialog, CreateEvalFormData } from '@sema4ai/spar-ui';
import {
  useScenariosQuery,
  getLatestScenarioRunQueryOptions,
  useCreateScenarioMutation,
  useDeleteScenarioMutation,
  useCreateScenarioRunMutation,
  usePollScenarioRun,
  useSuggestScenarioMutation,
} from '~/queries/evals';
import { Sidebar } from '~/components/Sidebar';
import { downloadJSON, transformAgentServerScenarios } from '~/lib/utils';
import { queryClient } from '~/components/providers/QueryClient';

export const Route = createFileRoute('/tenants/$tenantId/conversational/$agentId/$threadId/evaluations/')({
  component: RouteComponent,
});

function RouteComponent() {
  const { threadId, agentId, tenantId } = Route.useParams();
  const { addSnackbar } = useSnackbar();
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const navigate = useNavigate();

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ scenarioId: string; name: string } | null>(null);
  const [suggestedValues, setSuggestedValues] = useState<Partial<CreateEvalFormData> | undefined>(undefined);
  const [isFetchingSuggestion, setIsFetchingSuggestion] = useState(false);

  const { data: scenarios = [], isLoading: scenariosLoading } = useScenariosQuery({
    tenantId,
    agentId,
  });
  const createScenarioMutation = useCreateScenarioMutation();
  const deleteScenarioMutation = useDeleteScenarioMutation();
  const createScenarioRunMutation = useCreateScenarioRunMutation();
  const suggestScenarioMutation = useSuggestScenarioMutation();
  const { pollForCompletion } = usePollScenarioRun();

  const latestRunQueries = useQueries({
    queries: scenarios.map((scenario) =>
      getLatestScenarioRunQueryOptions({
        tenantId,
        scenarioId: scenario.scenario_id,
        agentAPIClient,
      }),
    ),
  });
  const latestRunsData = latestRunQueries.map((query) => query.data ?? null);
  const latestRunsLoading = latestRunQueries.some((query) => query.isLoading);

  const evaluations = useMemo(() => {
    return transformAgentServerScenarios(scenarios, latestRunsData);
  }, [scenarios, latestRunsData]);

  const handleCreateEvaluation = async (data: CreateEvalFormData) => {
    await createScenarioMutation.mutateAsync({
      tenantId,
      body: {
        name: data.name,
        description: data.description,
        thread_id: threadId,
      },
    });
    setCreateDialogOpen(false);
    setSuggestedValues(undefined);
    setIsFetchingSuggestion(false);
  };

  const handleAddEvaluation = async () => {
    setCreateDialogOpen(true);
    setIsFetchingSuggestion(true);
    setSuggestedValues(undefined);

    try {
      const suggestion = await suggestScenarioMutation.mutateAsync({
        tenantId,
        body: {
          thread_id: threadId,
          max_options: 1,
        },
      });

      setSuggestedValues({
        name: suggestion.name,
        description: suggestion.description,
      });
    } catch (_error) {
      addSnackbar({
        message: 'Could not generate suggestion, but you can still create an evaluation manually',
        variant: 'danger',
      });
      setSuggestedValues(undefined);
    } finally {
      setIsFetchingSuggestion(false);
    }
  };

  const handleRunTest = async (
    scenario: {
      scenarioId: string;
      name: string;
      description: string;
      threadId: string | null;
    },
    numTrials: number = 1,
  ) => {
    try {
      await createScenarioRunMutation.mutateAsync({
        tenantId,
        scenarioId: scenario.scenarioId,
        body: { num_trials: numTrials },
      });

      await pollForCompletion(scenario.scenarioId, tenantId);

      await queryClient.invalidateQueries({ queryKey: ['threads', agentId] });
    } catch {
      addSnackbar({
        message: `Failed to run test for "${scenario.name}"`,
        variant: 'danger',
      });
    }
  };

  const handleRunAll = (numTrials: number = 1) => {
    evaluations.forEach(({ scenario }) => handleRunTest(scenario, numTrials));
  };

  const handleDeleteRequest = (scenario: {
    scenarioId: string;
    name: string;
    description: string;
    threadId: string | null;
  }) => {
    setDeleteTarget({ scenarioId: scenario.scenarioId, name: scenario.name });
  };

  const handleViewResults = (trial: { threadId: string }) => {
    if (trial.threadId) {
      navigate({
        to: '/tenants/$tenantId/conversational/$agentId/$threadId',
        params: {
          tenantId,
          agentId,
          threadId: trial.threadId,
        },
      });
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;

    await deleteScenarioMutation.mutateAsync({
      tenantId,
      scenarioId: deleteTarget.scenarioId,
    });

    setDeleteTarget(null);
  };

  const handleDownloadScenario = (scenario: {
    scenarioId: string;
    name: string;
    description: string;
    threadId: string | null;
  }) => {
    const evaluation = evaluations.find((evaluation) => evaluation.scenario.scenarioId === scenario.scenarioId);

    if (!evaluation) {
      addSnackbar({
        message: 'Scenario data not found',
        variant: 'danger',
      });
      return;
    }

    const scenarioData = {
      scenario: evaluation.scenario,
      latestRun: evaluation.latestRun,
    };

    const filename = `${scenario.name.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_scenario`;

    downloadJSON(scenarioData, {
      filename,
      addTimestamp: true,
    });

    addSnackbar({
      message: `Scenario "${scenario.name}" downloaded successfully`,
      variant: 'success',
    });
  };

  return (
    <Sidebar name="Evaluations">
      <EvalSidebarView
        evaluations={evaluations}
        loading={scenariosLoading || latestRunsLoading}
        onRunTest={handleRunTest}
        onRunAll={handleRunAll}
        onDeleteScenario={handleDeleteRequest}
        onViewResults={handleViewResults}
        onDownloadScenario={handleDownloadScenario}
        onAddEvaluation={handleAddEvaluation}
      />

      <CreateEvalDialog
        open={createDialogOpen}
        onClose={() => {
          setCreateDialogOpen(false);
          setSuggestedValues(undefined);
          setIsFetchingSuggestion(false);
        }}
        onSubmit={handleCreateEvaluation}
        isLoading={createScenarioMutation.isPending}
        initialValues={suggestedValues}
        isFetchingSuggestion={isFetchingSuggestion}
      />

      {deleteTarget && (
        <Dialog open onClose={() => setDeleteTarget(null)}>
          <Dialog.Header>
            <Dialog.Header.Title title="Delete Evaluation" />
          </Dialog.Header>
          <Dialog.Content>
            Are you sure you want to delete "{deleteTarget.name}"? This action cannot be undone.
          </Dialog.Content>
          <Dialog.Actions>
            <Button loading={deleteScenarioMutation.isPending} onClick={handleDeleteConfirm}>
              Delete
            </Button>
            <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
          </Dialog.Actions>
        </Dialog>
      )}
    </Sidebar>
  );
}
