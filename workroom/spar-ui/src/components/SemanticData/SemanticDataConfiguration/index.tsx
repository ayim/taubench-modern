import { FC, useEffect, useMemo, useState } from 'react';
import { Dialog, Form, Progress, StepProps, Steps, useSnackbar } from '@sema4ai/components';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { useParams } from '../../../hooks';
import {
  useCreateSemanticDataMutation,
  useSemanticModelQuery,
  useUpdateSemanticDataModelMutation,
  useDataConnectionDatabaseInspectMutation,
  useImportSemanticDataModelMutation,
} from '../../../queries';
import {
  ConfigurationStep,
  DatabaseInspectionState,
  DataConnectionFormContext,
  DataConnectionFormSchema,
  DataSourceType,
  defaultFormDataValues,
  hasDataSelectionChanged,
  semanticModelToFormSchema,
  tablesToDataSelection,
} from './components/form';
import { DataConnection } from './components/DataConnection';
import { DataSelection } from './components/DataSelection';
import { ModelEdition } from './components/ModelEdition';
import { Processing } from './components/Processing';
import { SuccessView } from './components/SuccessView';

type Props = {
  onClose: () => void;
  modelId?: string;
};

export const SemanticDataConfiguration: FC<Props> = ({ onClose, modelId: initialModelId }) => {
  const [modelId, setModelId] = useState<string | undefined>(initialModelId);
  const { agentId } = useParams('/thread/$agentId');

  const [activeStep, setActiveStep] = useState<ConfigurationStep>(
    initialModelId ? ConfigurationStep.ModelEdition : ConfigurationStep.DataConnection,
  );
  const { addSnackbar } = useSnackbar();
  const [databaseInspectionState, setDatabaseInspectionState] = useState<DatabaseInspectionState>({
    isLoading: false,
    error: undefined,
    dataTables: [],
  });
  const [dataSourceType, setDataSourceType] = useState<DataSourceType | undefined>(undefined);

  const { data: semanticModel, isLoading: isLoadingSemanticModel } = useSemanticModelQuery(
    { modelId: modelId || '' },
    { enabled: !!modelId },
  );

  const { mutate: createSemanticData, isPending: isCreatePending } = useCreateSemanticDataMutation({});
  const { mutate: updateSemanticData, isPending: isUpdatePending } = useUpdateSemanticDataModelMutation({});
  const { mutateAsync: inspectDataConnection } = useDataConnectionDatabaseInspectMutation({});
  const { mutateAsync: importSemanticDataModel } = useImportSemanticDataModelMutation({});

  const isPending = isCreatePending || isUpdatePending;

  const formMethods = useForm<DataConnectionFormSchema>({
    resolver: zodResolver(DataConnectionFormSchema),
    defaultValues: defaultFormDataValues,
  });

  useEffect(() => {
    if (semanticModel) {
      const values = semanticModelToFormSchema(semanticModel);
      formMethods.reset(values);

      if (values.dataConnectionId) {
        setDataSourceType(DataSourceType.Database);
      } else {
        setDataSourceType(DataSourceType.File);
      }
    }
  }, [semanticModel]);

  const onSubmit = formMethods.handleSubmit(async (values) => {
    if (modelId) {
      const shouldRegenerateModel = hasDataSelectionChanged(values);

      updateSemanticData(
        { ...values, modelId, agentId, shouldRegenerateModel },
        {
          onSuccess: () => {
            if (shouldRegenerateModel) {
              setActiveStep(ConfigurationStep.Success);
            } else {
              addSnackbar({ message: 'Data model updated successfully', variant: 'success' });
              onClose();
            }
          },
          onError: (error) => {
            addSnackbar({ message: error.message, variant: 'danger' });
          },
        },
      );
    } else if (dataSourceType === DataSourceType.Import) {
      await importSemanticDataModel(
        { ...values, agentId },
        {
          onSuccess: (result) => {
            setActiveStep(ConfigurationStep.Success);
            setModelId(result.semantic_data_model_id);
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
          onSuccess: (result) => {
            setActiveStep(ConfigurationStep.Success);
            setModelId(result.semantic_data_model_id);
          },
          onError: (error) => {
            addSnackbar({ message: error.message, variant: 'danger' });
          },
        },
      );
    }
  });

  const formContextValue = useMemo(
    () => ({ databaseInspectionState, setDatabaseInspectionState, onSubmit }),
    [databaseInspectionState, onSubmit],
  );

  const { fileRefId, dataConnectionId, dataSelection, tables } = formMethods.watch();

  useEffect(() => {
    const inspect = async () => {
      if (dataConnectionId) {
        setDatabaseInspectionState({
          isLoading: true,
          error: undefined,
          dataTables: [],
        });

        await inspectDataConnection(
          { dataConnectionId },
          {
            onError: (error) => {
              setDatabaseInspectionState({
                isLoading: false,
                error: error.message,
                dataTables: [],
              });
              if (!initialModelId) {
                setActiveStep(ConfigurationStep.DataConnection);
              }
            },
            onSuccess: (result) => {
              setDatabaseInspectionState({
                isLoading: false,
                error: undefined,
                dataTables: result,
              });
              formMethods.setValue('dataSelection', tablesToDataSelection(result));
            },
          },
        );
      }
    };
    inspect();
  }, [dataConnectionId]);

  const onResetImport = () => {
    formMethods.reset(defaultFormDataValues);
  };

  const connectionStepProps: StepProps & { label: string } = (() => {
    if (dataSourceType === DataSourceType.Import) {
      return {
        status: tables ? 'completed' : 'incomplete',
        onClick: () => onResetImport(),
        label: 'File Upload',
      };
    }

    if (databaseInspectionState.error) {
      return {
        status: 'error',
        label: 'Connection',
      };
    }

    return {
      status: fileRefId || dataConnectionId ? 'completed' : 'incomplete',
      label: 'Connection',
    };
  })();

  const dataSelectionStepProps: StepProps & { label: string } = (() => {
    if (dataSourceType === DataSourceType.Import) {
      return {
        status: fileRefId || dataConnectionId ? 'completed' : 'incomplete',
        disabled: !tables,
        label: 'Connection',
      };
    }

    return {
      status: dataSelection.length > 0 ? 'completed' : 'incomplete',
      disabled: (!fileRefId && !dataConnectionId) || !!databaseInspectionState.error,
      label: 'Data Selection',
    };
  })();

  const modelEditionStepProps: StepProps & { label: string } = (() => {
    return {
      status: modelId || isCreatePending ? 'completed' : 'incomplete',
      label: 'Data Model',
      disabled: !modelId,
    };
  })();

  if (isLoadingSemanticModel && initialModelId === modelId) {
    return <Progress variant="page" />;
  }

  return (
    <Dialog size="page" onClose={onClose} open>
      <Form busy={isPending} onSubmit={onSubmit}>
        <FormProvider {...formMethods}>
          <DataConnectionFormContext.Provider value={formContextValue}>
            {activeStep !== ConfigurationStep.Success && (
              <Dialog.Bar>
                <Steps activeStep={activeStep} setActiveStep={setActiveStep}>
                  <Steps.Step {...connectionStepProps}>{connectionStepProps.label}</Steps.Step>
                  <Steps.Step {...dataSelectionStepProps}>{dataSelectionStepProps.label}</Steps.Step>
                  <Steps.Step {...modelEditionStepProps}>{modelEditionStepProps.label}</Steps.Step>
                </Steps>
              </Dialog.Bar>
            )}
            {isPending && activeStep === ConfigurationStep.DataSelection ? (
              <Processing />
            ) : (
              <>
                {activeStep === ConfigurationStep.DataConnection && (
                  <DataConnection
                    onClose={onClose}
                    setActiveStep={setActiveStep}
                    setDataSourceType={setDataSourceType}
                    dataSourceType={dataSourceType}
                  />
                )}
                {activeStep === ConfigurationStep.DataSelection && (
                  <DataSelection onClose={onClose} setActiveStep={setActiveStep} />
                )}
                {activeStep === ConfigurationStep.ModelEdition && modelId && (
                  <ModelEdition onClose={onClose} setActiveStep={setActiveStep} modelId={modelId} />
                )}
                {activeStep === ConfigurationStep.Success && (
                  <SuccessView onClose={onClose} setActiveStep={setActiveStep} modelName={semanticModel?.name} />
                )}
              </>
            )}
          </DataConnectionFormContext.Provider>
        </FormProvider>
      </Form>
    </Dialog>
  );
};
