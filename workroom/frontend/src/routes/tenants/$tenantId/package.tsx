import { useCallback, useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Box, Code, Dropzone, Typography, useSnackbar } from '@sema4ai/components';
import { Agent } from '@sema4ai/agent-server-interface';
import { getSnackbarContent } from '~/queries/shared';
import { useReadPackageMutation, usePackageMetadataMutation } from '~/queries/packages';

export const Route = createFileRoute('/tenants/$tenantId/package')({
  component: PackagePage,
});

function PackagePage() {
  const { addSnackbar } = useSnackbar();
  const readPackageMutation = useReadPackageMutation({});
  const packageMetadataMutation = usePackageMetadataMutation({});

  const [packageReadResult, setPackageReadResult] = useState<{
    status: 'success' | 'error';
    data: unknown;
  } | null>(null);
  const [packageMetadataResult, setPackageMetadataResult] = useState<{
    status: 'success' | 'error';
    data: Agent | unknown;
  } | null>(null);

  const handleDrop4Read = useCallback(
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
            setPackageReadResult({ status: 'success', data });
          },
          onError: (error) => {
            setPackageReadResult({ status: 'error', data: error });
            addSnackbar(getSnackbarContent(error));
          },
        },
      );
    },
    [readPackageMutation, addSnackbar],
  );

  const handleDrop4Metadata = useCallback(
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

      packageMetadataMutation.mutate(
        { formData },
        {
          onSuccess: (response) => {
            setPackageMetadataResult({ status: 'success', data: response });
          },
          onError: (error) => {
            setPackageMetadataResult({ status: 'error', data: error });
            addSnackbar(getSnackbarContent(error));
          },
        },
      );
    },
    [packageMetadataMutation, addSnackbar],
  );

  return (
    <Box display="flex" flexDirection="column" gap="$32" padding={4}>
      <Box display="flex" flexDirection="column" gap="$16" borderColor="border.subtle" borderRadius="$16" p="$16">
        <Typography as="h3">Package Read: POST /api/v2/package/read</Typography>
        <Box maxWidth={600}>
          <Dropzone
            onDrop={handleDrop4Read}
            title={<span>Drag & drop or select a ZIP file to read package</span>}
            dropTitle="Drop your package here"
            disabled={readPackageMutation.isPending}
            dropzoneConfig={{
              accept: { 'application/zip': ['.zip'] },
              maxSize: 100_000_000,
            }}
          />
        </Box>
        {packageReadResult && (
          <Box maxWidth={600}>
            <Code
              aria-labelledby="package-read-result"
              title={packageReadResult.status === 'success' ? 'Package Read: SUCCESS' : 'Package Read: ERROR'}
              value={JSON.stringify(packageReadResult.data, null, 2)}
            />
          </Box>
        )}
      </Box>
      <Box display="flex" flexDirection="column" gap="$16" borderColor="border.subtle" borderRadius="$16" p="$16">
        <Typography as="h2">Package Metadata: POST /api/v2/package/metadata</Typography>
        <Box maxWidth={600}>
          <Dropzone
            onDrop={handleDrop4Metadata}
            title={<span>Drag & drop or select a ZIP file to generate package metadata</span>}
            dropTitle="Drop your package here"
            disabled={packageMetadataMutation.isPending}
            dropzoneConfig={{
              accept: { 'application/zip': ['.zip'] },
              maxSize: 100_000_000,
            }}
          />
        </Box>
        {packageMetadataResult && (
          <Box maxWidth={600}>
            <Code
              aria-labelledby="package-metadata-result"
              title={
                packageMetadataResult.status === 'success' ? 'Package Metadata: SUCCESS' : 'Package Metadata: ERROR'
              }
              value={JSON.stringify(packageMetadataResult.data, null, 2)}
            />
          </Box>
        )}
      </Box>
    </Box>
  );
}
