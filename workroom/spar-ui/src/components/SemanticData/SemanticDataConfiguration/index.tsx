import { FC, useEffect, useState } from 'react';
import { Dialog, Form, Steps, useSnackbar } from '@sema4ai/components';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { useParams } from '../../../hooks';
import {
  useCreateSemanticDataMutation,
  useSemanticModelQuery,
  useUpdateSemanticDataModelMutation,
} from '../../../queries/semanticData';
import { ConfigurationStep, DataConnectionFormSchema } from './components/form';
import { DataConnection } from './components/DataConnection';
import { DataSelection } from './components/DataSelection';
import { ModelEdition } from './components/ModelEdition';

type Props = {
  onClose: () => void;
  modelId?: string;
};

export const SemanticDataConfiguration: FC<Props> = ({ onClose, modelId }) => {
  const { agentId } = useParams('/thread/$agentId');
  const [activeStep, setActiveStep] = useState<ConfigurationStep>(ConfigurationStep.DataConnection);
  const { addSnackbar } = useSnackbar();

  const { data: semanticModel } = useSemanticModelQuery({ modelId: modelId || '' }, { enabled: !!modelId });

  const { mutate: createSemanticData, isPending: isCreatePending } = useCreateSemanticDataMutation({});
  const { mutate: updateSemanticData, isPending: isUpdatePending } = useUpdateSemanticDataModelMutation({});

  const isPending = isCreatePending || isUpdatePending;

  const formMethods = useForm<DataConnectionFormSchema>({
    resolver: zodResolver(DataConnectionFormSchema),
    defaultValues: {
      dataConnectionId: '',
      description: '',
      dataSelection: [],
    },
  });

  useEffect(() => {
    if (semanticModel) {
      const values = {
        name: semanticModel.name,
        dataConnectionId: semanticModel.tables[0].base_table.data_connection_id,
        description: semanticModel.description,
        dataSelection: semanticModel.tables.map((table) => {
          return {
            name: table.name,
            columns: table.dimensions.map((dimension) => {
              return {
                name: dimension.name,
                data_type: dimension.data_type,
              };
            }),
          };
        }),
        tables: semanticModel.tables,
      };

      formMethods.reset(values);
      setActiveStep(ConfigurationStep.ModelEdition);
    }
  }, [semanticModel]);

  const onSubmit = formMethods.handleSubmit(async (values) => {
    if (modelId) {
      updateSemanticData(
        { ...values, modelId, agentId },
        {
          onSuccess: () => {
            addSnackbar({ message: 'Semantic data model updated successfully', variant: 'success' });
            onClose();
          },
          onError: (error) => {
            addSnackbar({ message: error.message, variant: 'danger' });
          },
        },
      );
    } else {
      createSemanticData(
        { ...values, agentId },
        {
          onSuccess: () => {
            addSnackbar({
              message: `Semantic data model ${modelId ? 'updated' : 'created'} successfully`,
              variant: 'success',
            });
            onClose();
          },
          onError: (error) => {
            addSnackbar({ message: error.message, variant: 'danger' });
          },
        },
      );
    }
  });

  const step1Status = formMethods.watch('dataConnectionId') ? 'completed' : 'incomplete';
  const step2Status = formMethods.watch('dataSelection')?.length > 0 ? 'completed' : 'incomplete';
  const step3Status = modelId ? 'completed' : 'incomplete';

  return (
    <Dialog size="page" onClose={onClose} open>
      <Form busy={isPending} onSubmit={onSubmit}>
        <FormProvider {...formMethods}>
          <Dialog.Bar>
            <Steps activeStep={activeStep} setActiveStep={setActiveStep}>
              <Steps.Step status={step1Status}>Connection</Steps.Step>
              <Steps.Step status={step2Status} disabled={step1Status !== 'completed'}>
                Data Selection
              </Steps.Step>
              <Steps.Step status={step3Status} disabled={step2Status !== 'completed'}>
                Data Model
              </Steps.Step>
            </Steps>
          </Dialog.Bar>
          {activeStep === ConfigurationStep.DataConnection && (
            <DataConnection onClose={onClose} setActiveStep={setActiveStep} />
          )}
          {activeStep === ConfigurationStep.DataSelection && (
            <DataSelection onClose={onClose} setActiveStep={setActiveStep} />
          )}
          {activeStep === ConfigurationStep.ModelEdition && (
            <ModelEdition onClose={onClose} setActiveStep={setActiveStep} />
          )}
        </FormProvider>
      </Form>
    </Dialog>
  );
};
