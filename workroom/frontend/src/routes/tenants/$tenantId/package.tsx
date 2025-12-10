import { useCallback, useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Box, Dropzone, Typography, useSnackbar } from '@sema4ai/components';
import { Agent } from '@sema4ai/agent-server-interface';
import { useSparUIContext, getSnackbarContent } from '@sema4ai/spar-ui';
import { useReadPackageMutation } from '@sema4ai/spar-ui/queries';

export const Route = createFileRoute('/tenants/$tenantId/package')({
  component: PackagePage,
});

function PackagePage() {
  const { sparAPIClient } = useSparUIContext();
  const { addSnackbar } = useSnackbar();
  const readPackageMutation = useReadPackageMutation({ sparAPIClient });
  const [packageData, setPackageData] = useState<Agent | null>(null);

  const handleDrop = useCallback(
    async (files: File[]) => {
      const file = files[0];
      if (!file) {
        return;
      }

      if (!file.name.toLowerCase().endsWith('.zip')) {
        addSnackbar({
          message: 'Invalid file type. Only ZIP files are allowed.',
          variant: 'danger',
        });
        return;
      }

      const formData = new FormData();
      formData.append('package_zip_file', file, file.name);

      readPackageMutation.mutate(
        { formData },
        {
          onSuccess: (data) => {
            setPackageData(data);
          },
          onError: (error) => {
            addSnackbar(getSnackbarContent(error));
          },
        },
      );
    },
    [readPackageMutation, addSnackbar],
  );

  return (
    <Box display="flex" flexDirection="column" gap={4} padding={4} height="100%">
      <Typography as="h2" pb="$8">
        Package Read: POST /api/v2/package/read
      </Typography>
      <Box maxWidth={600}>
        <Dropzone
          onDrop={handleDrop}
          title={<span>Drag & drop or select a ZIP file to read package</span>}
          dropTitle="Drop your package here"
          disabled={readPackageMutation.isPending}
          dropzoneConfig={{
            accept: { 'application/zip': ['.zip'] },
            maxSize: 100_000_000,
          }}
        />
      </Box>
      {packageData && (
        <Box>
          <Typography>Package Data</Typography>
          <pre>{JSON.stringify(packageData, null, 2)}</pre>
        </Box>
      )}
    </Box>
  );
}
