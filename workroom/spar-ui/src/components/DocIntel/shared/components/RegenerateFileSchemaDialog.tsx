import { FC, useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import z from 'zod';
import { Button, Dialog, Form, Input } from '@sema4ai/components';

import { Code } from '../../../../common/code';
import { useGetSchemaQuery } from '../../../../queries/documentIntelligence';

const formSchema = z.object({
  context: z.string(),
  schema: z.string(),
});

type FormData = z.infer<typeof formSchema>;

const safeStringify = (value: unknown, fallback = ''): string => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return typeof value === 'object' ? fallback : String(value ?? fallback);
  }
};

const getSchemaInstructions = ({ context, schema }: { context: string; schema: string }) => {
  return `
      # Instructions
      ${context || 'regenerate schema'}

      # Schema reference
      \`\`\`json
      ${schema}
      \`\`\`
        `;
};

interface Props {
  onGenerateSchema: (data?: { instructions?: string; force: boolean }) => Promise<void | null>;
  open: boolean;
  onClose: () => void;
  fileName: string;
  threadId: string;
  agentId: string;
  isGeneratingSchema: boolean;
  isExtracting: boolean;
  userPrompt?: string | null;
}

const Content: FC<Omit<Props, 'open' | 'schema'>> = ({
  fileName,
  threadId,
  agentId,
  onClose,
  onGenerateSchema,
  isGeneratingSchema,
  isExtracting,
  userPrompt,
}) => {
  const { data: schemaData, isLoading: isLoadingSchema } = useGetSchemaQuery({ fileName, threadId, agentId });

  const {
    handleSubmit,
    control,
    register,
    formState: { errors, isSubmitting },
    getFieldState,
    setValue,
  } = useForm({
    resolver: zodResolver(formSchema),
    defaultValues: {
      context: userPrompt ?? '',
      schema: schemaData ? safeStringify(schemaData.schema.extract_schema ?? schemaData.schema) : '',
    },
  });

  // Pre-populate context from userPrompt when it becomes available
  useEffect(() => {
    if (userPrompt && !getFieldState('context').isDirty) {
      setValue('context', userPrompt, { shouldDirty: false });
    }
  }, [userPrompt, getFieldState, setValue]);

  useEffect(() => {
    if (schemaData && !getFieldState('schema').isDirty) {
      setValue('schema', safeStringify(schemaData.schema.extract_schema ?? schemaData), { shouldDirty: false });
    }
  }, [schemaData, getFieldState, setValue]);

  const shouldCloseEarly = isSubmitting && isGeneratingSchema;
  useEffect(() => {
    if (shouldCloseEarly) {
      onClose();
    }
  }, [shouldCloseEarly]);

  const onSubmit = async (data: FormData) => {
    await onGenerateSchema({
      force: true,
      instructions: getSchemaInstructions({ context: data.context, schema: data.schema }),
    });

    onClose();
  };

  const isLoading = isSubmitting || isLoadingSchema;
  return (
    <Form onSubmit={handleSubmit(onSubmit)} busy={isLoading}>
      <Dialog.Content>
        <Form.Fieldset>
          <Input
            {...register('context')}
            error={errors.context?.message}
            label="Instructions"
            placeholder="Instructions for schema generation..."
            type="textarea"
            rows={6}
          />
        </Form.Fieldset>

        <Form.Fieldset>
          <Controller
            name="schema"
            control={control}
            render={({ field: { value, onChange, onBlur }, fieldState: { error } }) =>
              isLoadingSchema ? (
                <Code label="Existing schema" lang="json" value="loading schema..." rows={10} lineNumbers readOnly />
              ) : (
                <Code
                  label="Existing schema"
                  lang="json"
                  value={value}
                  rows={10}
                  onChange={onChange}
                  onBlur={onBlur}
                  error={error?.message}
                  lineNumbers
                />
              )
            }
          />
        </Form.Fieldset>
      </Dialog.Content>
      <Dialog.Actions>
        <Button type="submit" variant="primary" disabled={isLoading || isExtracting} loading={isLoading} round>
          Submit
        </Button>
        <Button variant="secondary" onClick={onClose} disabled={isSubmitting} round>
          Cancel
        </Button>
      </Dialog.Actions>
    </Form>
  );
};

export const RegenerateFileSchemaDialog: FC<Props> = ({ open, onClose, userPrompt, ...props }) => (
  <Dialog open={open} onClose={onClose} size="medium" width="800px">
    <Dialog.Header>
      <Dialog.Header.Title title="Generate new schema" />
    </Dialog.Header>
    <Content {...props} onClose={onClose} userPrompt={userPrompt} />
  </Dialog>
);
