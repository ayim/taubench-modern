import { Box, Button, EmptyState, useSnackbar } from '@sema4ai/components';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createFileRoute, Outlet, useNavigate, useParams, useRouteContext, useRouter } from '@tanstack/react-router';
import { useAgentsQuery, agentsQueryKey } from '@sema4ai/spar-ui/queries';

import { AgentDeploymentForm } from './deploy/components/AgentDeploymentForm';
import { AgentDeploymentFormSchema } from './deploy/components/context';
import { mcpHeadersFromRecord } from '~/lib/utils';
import { getListMcpServersQueryOptions } from '~/queries/mcpServers';
import { useGetAgentPackageUpload } from '~/queries/agentPackageUpload';
import { IconFileError } from '@sema4ai/icons';

export const Route = createFileRoute('/tenants/$tenantId/agents/deploy')({
  loader: async ({ context: { agentAPIClient, queryClient }, params: { tenantId } }) => {
    const mcpServers = await queryClient.ensureQueryData(getListMcpServersQueryOptions({ agentAPIClient, tenantId }));
    return { mcpServers };
  },
  component: CreateAgentIndex,
});

function buildAgentPackagePayload(form: AgentDeploymentFormSchema) {
  const mcpServerSettings = form.mcpServerSettings ?? [];

  // Separate inline vs global servers based on presence of mcpServerId
  const inlineMcpServers = mcpServerSettings
    .filter((server) => !server.mcpServerId)
    .map((server) => ({
      name: server.name,
      type: server.type ?? 'generic_mcp',
      transport: server.transport,
      url: server.url ?? null,
      headers: mcpHeadersFromRecord(server.headers),
      force_serial_tool_calls: server.force_serial_tool_calls,
    }));

  const configuredMCPServerIds = mcpServerSettings.map((server) => server.mcpServerId).filter(Boolean);

  const payload = {
    name: form.name,
    description: form.description,
    public: true,
    platform_params_ids: [form.llmId],
    action_servers: [],
    mcp_servers: inlineMcpServers,
    mcp_server_ids: configuredMCPServerIds,
    selected_tools: form.selected_tools || { tool_names: [] },
  };

  return payload;
}

function CreateAgentIndex() {
  const { tenantId } = useParams({ from: '/tenants/$tenantId/agents/deploy' });
  const { agentAPIClient } = useRouteContext({ from: '/tenants/$tenantId' });
  const navigate = useNavigate();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { addSnackbar } = useSnackbar();
  const uploadedAgentPackage = useGetAgentPackageUpload(tenantId);

  const deployMutation = useMutation({
    mutationFn: async (payload: AgentDeploymentFormSchema) => {
      if (!uploadedAgentPackage) {
        throw new Error('Provide a package file to upload');
      }

      const jsonPayload = buildAgentPackagePayload(payload);

      const formData = new FormData();
      formData.append('package_zip_file', uploadedAgentPackage.file, uploadedAgentPackage.file.name);

      for (const [fieldName, fieldValue] of Object.entries(jsonPayload)) {
        const value = typeof fieldValue === 'string' ? fieldValue : JSON.stringify(fieldValue);
        formData.append(fieldName, value);
      }

      const response = await agentAPIClient.deployAgentFromPackageMultipart(tenantId, formData);

      return response;
    },
    onSuccess: async (deployedAgent) => {
      addSnackbar({
        message: 'Agent deployed successfully',
        variant: 'success',
      });

      const agentId = deployedAgent.agent_id;
      await queryClient.invalidateQueries({ queryKey: agentsQueryKey() });
      await router.invalidate();

      navigate({ to: '/tenants/$tenantId/conversational/$agentId', params: { tenantId, agentId } });
    },
    onError: (error: unknown) => {
      addSnackbar({
        message: error instanceof Error ? error.message : 'Failed to deploy agent',
        variant: 'danger',
      });
    },
  });

  const onSubmit = async (payload: AgentDeploymentFormSchema) => {
    if (!uploadedAgentPackage) {
      addSnackbar({
        message: 'Provide a package file to upload',
        variant: 'danger',
      });
      return;
    }
    await deployMutation.mutateAsync(payload);
  };

  const { data: agents } = useAgentsQuery({});
  const existingAgentNames = agents?.map((agent) => agent.name) ?? [];

  if (!uploadedAgentPackage) {
    return (
      <Box height="100%" display="flex" alignItems="center" justifyContent="center">
        <EmptyState
          illustration={<IconFileError size={100} />}
          title="No Agent Package Found"
          description="Please go back to the home page and upload an agent package first."
          action={
            <Button round onClick={() => navigate({ to: '/tenants/$tenantId/home', params: { tenantId } })}>
              Return to Home
            </Button>
          }
        />
        <Outlet />
      </Box>
    );
  }

  return (
    <Box height="100%">
      <Box px="$40" py="$64" maxWidth={768} margin="0 auto">
        <AgentDeploymentForm
          agentTemplate={uploadedAgentPackage.fileContent.agentTemplate}
          defaultValues={uploadedAgentPackage.fileContent.defaultValues}
          onSubmit={onSubmit}
          isPending={deployMutation.isPending}
          title="Deploy Agent"
          existingAgentNames={existingAgentNames}
        />
        <Outlet />
      </Box>
    </Box>
  );
}
