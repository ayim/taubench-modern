import { Card, Progress, useSnackbar } from '@sema4ai/components';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { FileRejection, useDropzone } from 'react-dropzone';
import { IconUpload } from '@sema4ai/icons';
import { AgentPackageInspectionResponse, useInspectAgentPackageMutation } from '@sema4ai/spar-ui/queries';
import { useSparUIContext } from '@sema4ai/spar-ui';

type Props = {
  setAgentPackageUploadData: (data: {
    agentTemplate: NonNullable<AgentPackageInspectionResponse>;
    agentPackage: File;
  }) => void;
};

export const AgentUploadForm = ({ setAgentPackageUploadData }: Props) => {
  const { addSnackbar } = useSnackbar();
  const { sparAPIClient } = useSparUIContext();
  const { mutateAsync: inspectAgentPackageMutation, isPending } = useInspectAgentPackageMutation({ sparAPIClient });

  const schema = z.object({
    file: z
      .instanceof(File, { message: 'Please choose a file' })
      .refine((f) => f.name.toLowerCase().endsWith('.zip'), 'File type is not valid. Only ZIP files are allowed.'),
  });

  type FormValues = z.infer<typeof schema>;

  const { setValue, trigger } = useForm<FormValues>({ resolver: zodResolver(schema), mode: 'onChange' });

  const onDrop = async (files: File[], fileRejection: FileRejection[]) => {
    const file = files[0];

    const error = fileRejection?.[0]?.errors?.[0];
    if (error && error.message) {
      addSnackbar({
        message: error.message,
        variant: 'danger',
      });
      return;
    }

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
    } catch (err) {
      console.error('❌ Error processing ZIP file:', err);
      addSnackbar({
        message: 'Failed to process agent package. Please check the file format.',
        variant: 'danger',
      });
    }
  };

  const { getInputProps, open } = useDropzone({
    multiple: false,
    accept: {
      'application/zip': ['.zip'],
    },
    maxSize: 100_000_000,
    onDrop: onDrop,

    // Disable click and keydown behavior since we're using a button
    noClick: true,
    noKeyboard: true,
  });

  return (
    <>
      {isPending && <Progress variant="page" />}
      <input {...getInputProps()} />
      <Card
        as="button"
        title="Import Agent Package"
        icon={IconUpload}
        onClick={open}
        description="Upload an agent package."
      />
    </>
  );
};
