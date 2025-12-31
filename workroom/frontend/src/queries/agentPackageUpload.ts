import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';
import { AgentDeploymentFormSchema } from '~/routes/tenants/$tenantId/agents/deploy/components/context';
import { AgentPackageInspectionResponse } from '@sema4ai/spar-ui/queries';

const AGENT_PACKAGE_CACHE_KEY = 'agent-package-upload';

export type AgentPackageUploadData = {
  file: File;
  fileContent: {
    agentTemplate: NonNullable<AgentPackageInspectionResponse>;
    defaultValues: AgentDeploymentFormSchema;
  };
};

export const useUploadAgentPackageMutation = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: async ({ tenantId, data }: { tenantId: string; data: AgentPackageUploadData }) => {
      queryClient.setQueryData([AGENT_PACKAGE_CACHE_KEY, tenantId], data);
      return data;
    },
    onSuccess: (_data, { tenantId }) => {
      navigate({
        to: '/tenants/$tenantId/agents/deploy',
        params: { tenantId },
      });
    },
  });
};

export const useGetAgentPackageUpload = (tenantId: string) => {
  const queryClient = useQueryClient();

  return queryClient.getQueryData<AgentPackageUploadData>([AGENT_PACKAGE_CACHE_KEY, tenantId]) || null;
};
