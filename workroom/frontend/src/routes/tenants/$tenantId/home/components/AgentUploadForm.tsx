import { Dropzone, Typography, useSnackbar } from '@sema4ai/components';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

import { AgentPackageInspectionResponse, useInspectAgentPackageMutation } from '~/queries/agentPackageInspection';

type Props = {
  setAgentPackageUploadData: (data: {
    agentTemplate: NonNullable<AgentPackageInspectionResponse>;
    agentPackage: File;
  }) => void;
};

export const AgentUploadForm = ({ setAgentPackageUploadData }: Props) => {
  const { addSnackbar } = useSnackbar();
  const { mutateAsync: inspectAgentPackageMutation } = useInspectAgentPackageMutation({});

  const schema = z.object({
    file: z
      .instanceof(File, { message: 'Please choose a file' })
      .refine((f) => f.name.toLowerCase().endsWith('.zip'), 'File type is not valid. Only ZIP files are allowed.'),
  });

  type FormValues = z.infer<typeof schema>;

  const { setValue, trigger } = useForm<FormValues>({ resolver: zodResolver(schema), mode: 'onChange' });

  const onDrop = async (files: File[]) => {
    const file = files[0];

    if (!file) {
      return;
    }

    setValue('file', file, { shouldValidate: true });
    const valid = await trigger('file');
    if (!valid) return;

    try {
      const formData = new FormData();
      formData.append('package_zip_file', file, file.name);
      formData.append('name', file.name.replace(/\.zip$/i, ''));
      formData.append('description', 'Package uploaded from UI');

      const inspectionResult = await inspectAgentPackageMutation({ formData });

      if (inspectionResult.status === 'failure' || !inspectionResult.data) {
        throw new Error('Failed to inspect agent package: no data returned');
      }

      setAgentPackageUploadData({
        agentTemplate: inspectionResult.data,
        agentPackage: file,
      });
    } catch {
      addSnackbar({
        message: 'Failed to process agent package. Please check the file format.',
        variant: 'danger',
      });
    }
  };

  return (
    <Dropzone
      onDrop={onDrop}
      title={
        <span>
          Drag & drop or{' '}
          <Typography color="content.accent" as="span">
            select Agent .zip
          </Typography>{' '}
          to upload
        </span>
      }
      dropTitle="Drop your files here"
      description="Only supports ZIP files • Max size: 20MB"
      dropzoneConfig={{
        accept: {
          'application/zip': ['.zip'],
        },
        maxSize: 100_000_000,
      }}
    />
  );
};
