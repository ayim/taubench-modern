import { useMutation } from '@tanstack/react-query';
import { components } from '@sema4ai/agent-server-interface';
import { useSparUIContext } from '../../../api/context';
import { QueryError, ResourceType } from '../../../queries/shared';

type AgentPackageInspectionResponse = components['schemas']['AgentPackageInspectionResponse'];

type HostedMcpUploadResult = {
  file: File;
  data: AgentPackageInspectionResponse;
};

export type UseHostedMcpUploadResult = {
  file: File | null;
  inspectionData: AgentPackageInspectionResponse | null;
  isPending: boolean;
  error: QueryError | null;
  handleDrop: (files: File[]) => Promise<HostedMcpUploadResult | null>;
  reset: () => void;
};

export const useHostedMcpUpload = (): UseHostedMcpUploadResult => {
  const { sparAPIClient } = useSparUIContext();

  const mutation = useMutation<HostedMcpUploadResult, QueryError, File>({
    mutationFn: async (droppedFile: File) => {
      const isZip = droppedFile.name.toLowerCase().endsWith('.zip');
      if (!isZip) {
        throw new QueryError('File type is not valid. Only ZIP files are allowed.');
      }

      const formData = new FormData();
      formData.append('package_zip_file', droppedFile, droppedFile.name);
      formData.append('name', droppedFile.name.replace(/\.zip$/i, ''));
      formData.append('description', 'Agent package uploaded from UI');

      const response = await sparAPIClient.queryAgentServer('post', '/api/v2/package/inspect/agent', {
        params: {},
        body: formData as never,
      });

      if (!response.success) {
        throw new QueryError(response.message || 'Failed to inspect agent package', {
          code: response.code,
          resource: ResourceType.Agent,
        });
      }

      const result = response.data;
      if (result?.status === 'failure' || !result?.data) {
        throw new QueryError('Failed to inspect agent package: no data returned', {
          resource: ResourceType.Agent,
        });
      }

      return { file: droppedFile, data: result.data };
    },
  });

  const handleDrop = async (files: File[]): Promise<HostedMcpUploadResult | null> => {
    const droppedFile = files[0];
    if (!droppedFile) {
      return null;
    }

    return mutation.mutateAsync(droppedFile, {
      onError: () => {
        // Error is available via mutation.error
        return null;
      },
    });
  };

  return {
    file: mutation.data?.file ?? null,
    inspectionData: mutation.data?.data ?? null,
    isPending: mutation.isPending,
    error: mutation.error,
    handleDrop,
    reset: mutation.reset,
  };
};
