import { FC, useEffect, useState } from 'react';
import { Dialog, Form, Steps, useSnackbar } from '@sema4ai/components';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { useParams } from '../../../hooks';
import { useCreateSemanticDataMutation, useSemanticModelQuery } from '../../../queries/semanticData';
import { ConfigurationStep, DataConnectionFormSchema } from './components/form';
import { DataConnection } from './components/DataConnection';
import { DataSelection } from './components/DataSelection';
import { ModelCreation } from './components/ModelCreation';

type Props = {
  onClose: () => void;
  modelId?: string;
};

export const SemanticDataConfiguration: FC<Props> = ({ onClose, modelId }) => {
  const { agentId } = useParams('/thread/$agentId');
  const [activeStep, setActiveStep] = useState<ConfigurationStep>(ConfigurationStep.DataConnection);
  const { addSnackbar } = useSnackbar();

  const { data: semanticModel } = useSemanticModelQuery({ modelId: modelId || '' }, { enabled: !!modelId });

  const { mutate: createSemanticData, isPending } = useCreateSemanticDataMutation({});

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
      };

      formMethods.reset(values);
      setActiveStep(ConfigurationStep.DataSelection);
    }
  }, [semanticModel]);

  const onSubmit = formMethods.handleSubmit(async (values) => {
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
  });

  const step1Status = formMethods.watch('dataConnectionId') ? 'completed' : 'incomplete';

  return (
    <Dialog size="page" onClose={onClose} open>
      <Form busy={isPending} onSubmit={onSubmit}>
        <FormProvider {...formMethods}>
          <Dialog.Bar>
            <Steps activeStep={activeStep} setActiveStep={setActiveStep}>
              <Steps.Step status={step1Status}>Connection</Steps.Step>
              <Steps.Step disabled={step1Status !== 'completed'}>Data Selection</Steps.Step>
              <Steps.Step disabled>Data Model</Steps.Step>
            </Steps>
          </Dialog.Bar>
          {activeStep === ConfigurationStep.DataConnection && (
            <DataConnection onClose={onClose} setActiveStep={setActiveStep} />
          )}
          {activeStep === ConfigurationStep.DataSelection && (
            <DataSelection onClose={onClose} setActiveStep={setActiveStep} />
          )}
          {activeStep === ConfigurationStep.ModelCreation && (
            <ModelCreation onClose={onClose} setActiveStep={setActiveStep} />
          )}
        </FormProvider>
      </Form>
    </Dialog>
  );
};
