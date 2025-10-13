import { FC, useEffect, useMemo, useState } from 'react';
import { Box, Dialog, Form, Progress, Steps, Typography, useSnackbar } from '@sema4ai/components';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { useParams } from '../../../hooks';
import {
  useCreateSemanticDataMutation,
  useSemanticModelQuery,
  useUpdateSemanticDataModelMutation,
} from '../../../queries/semanticData';
import {
  ConfigurationStep,
  DataConnectionFormContext,
  DataConnectionFormSchema,
  InspectedTableInfo,
} from './components/form';
import { DataConnection } from './components/DataConnection';
import { DataSelection } from './components/DataSelection';
import { ModelEdition } from './components/ModelEdition';

type Props = {
  onClose: () => void;
  modelId?: string;
};

export const SemanticDataConfiguration: FC<Props> = ({ onClose, modelId }) => {
  const { agentId, threadId } = useParams('/thread/$agentId/$threadId');
  const [activeStep, setActiveStep] = useState<ConfigurationStep>(ConfigurationStep.DataConnection);
  const { addSnackbar } = useSnackbar();
  const [inspectedDataTables, setInspectedDataTables] = useState<InspectedTableInfo[]>([]);

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

  const formContextValue = useMemo(() => ({ inspectedDataTables, setInspectedDataTables }), [inspectedDataTables]);

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
        { ...values, agentId, threadId },
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

  const step1Status = inspectedDataTables.length > 0 ? 'completed' : 'incomplete';
  const step2Status = formMethods.watch('dataSelection')?.length > 0 ? 'completed' : 'incomplete';
  const step3Status = modelId || isCreatePending ? 'completed' : 'incomplete';

  return (
    <Dialog size="page" onClose={onClose} open>
      <Form busy={isPending} onSubmit={onSubmit}>
        <FormProvider {...formMethods}>
          <DataConnectionFormContext.Provider value={formContextValue}>
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
            {isCreatePending ? (
              <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" height="100%">
                <Typography variant="body-large" color="content.subtle">
                  Creating Semantic Data Model...
                </Typography>
                <Progress />
              </Box>
            ) : (
              <>
                {activeStep === ConfigurationStep.DataConnection && (
                  <DataConnection onClose={onClose} setActiveStep={setActiveStep} />
                )}
                {activeStep === ConfigurationStep.DataSelection && (
                  <DataSelection onClose={onClose} setActiveStep={setActiveStep} />
                )}
                {activeStep === ConfigurationStep.ModelEdition && (
                  <ModelEdition onClose={onClose} setActiveStep={setActiveStep} />
                )}
              </>
            )}
          </DataConnectionFormContext.Provider>
        </FormProvider>
      </Form>
    </Dialog>
  );
};
