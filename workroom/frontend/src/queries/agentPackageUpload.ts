import { queryOptions, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from '@tanstack/react-router';
import type { AgentPackageResponse } from '~/routes/tenants/$tenantId/home/components/AgentUploadForm';
import { QueryProps } from './shared';

const AGENT_PACKAGE_CACHE_KEY = 'agent-package-upload';

export type AgentPackageUploadData = {
  file: File;
  fileContent: AgentPackageResponse;
};

export const getAgentPackageUploadQueryOptions = ({ tenantId }: QueryProps<{ tenantId: string }>) =>
  queryOptions({
    queryKey: [AGENT_PACKAGE_CACHE_KEY, tenantId],
    queryFn: async (): Promise<AgentPackageUploadData | null> => {
      return null;
    },
    enabled: false,
  });

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
