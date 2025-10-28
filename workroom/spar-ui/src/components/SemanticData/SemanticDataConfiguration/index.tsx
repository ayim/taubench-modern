import { FC, useEffect, useMemo, useState } from 'react';
import { Dialog, Form, Progress, Steps, StepStatusType, useSnackbar } from '@sema4ai/components';
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
  semanticModelToFormSchema,
} from './components/form';
import { DataConnection } from './components/DataConnection';
import { DataSelection } from './components/DataSelection';
import { ModelEdition } from './components/ModelEdition';
import { Processing } from './components/Processing';

type Props = {
  onClose: () => void;
  modelId?: string;
};

export const SemanticDataConfiguration: FC<Props> = ({ onClose, modelId }) => {
  const { agentId } = useParams('/thread/$agentId');
  const [activeStep, setActiveStep] = useState<ConfigurationStep>(ConfigurationStep.DataConnection);
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
    defaultValues: {
      dataConnectionId: '',
      description: '',
      dataSelection: [],
    },
  });

  useEffect(() => {
    if (semanticModel) {
      const values = semanticModelToFormSchema(semanticModel);
      formMethods.reset(values);
      setActiveStep(ConfigurationStep.ModelEdition);

      if (values.dataConnectionId) {
        setDataSourceType(DataSourceType.Database);
      } else {
        setDataSourceType(DataSourceType.File);
      }
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
    } else if (dataSourceType === DataSourceType.Import) {
      await importSemanticDataModel(
        { ...values, agentId },
        {
          onSuccess: () => {
            addSnackbar({
              message: `Semantic data model imported successfully`,
              variant: 'success',
            });
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
              message: `Semantic data model created successfully`,
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
              setActiveStep(ConfigurationStep.DataConnection);
            },
            onSuccess: (result) => {
              setDatabaseInspectionState({
                isLoading: false,
                error: undefined,
                dataTables: result,
              });
            },
          },
        );
      }
    };
    inspect();
  }, [dataConnectionId]);

  const onResetImport = () => {
    formMethods.reset({
      dataConnectionId: undefined,
      fileRefId: undefined,
      tables: undefined,
      dataSelection: [],
      description: '',
    });
  };

  const [step1Status, step2Status, step3Status] = (() => {
    if (dataSourceType === DataSourceType.Import) {
      return [
        tables ? 'completed' : 'incomplete',
        fileRefId || dataConnectionId ? 'completed' : 'incomplete',
        modelId || isCreatePending ? 'completed' : 'incomplete',
      ] satisfies StepStatusType[];
    }

    return [
      fileRefId || dataConnectionId ? 'completed' : 'incomplete',
      dataSelection.length > 0 ? 'completed' : 'incomplete',
      modelId || isCreatePending ? 'completed' : 'incomplete',
    ] satisfies StepStatusType[];
  })();

  if (isLoadingSemanticModel) {
    return <Progress variant="page" />;
  }

  return (
    <Dialog size="page" onClose={onClose} open>
      <Form busy={isPending} onSubmit={onSubmit}>
        <FormProvider {...formMethods}>
          <DataConnectionFormContext.Provider value={formContextValue}>
            <Dialog.Bar>
              {(dataSourceType === DataSourceType.Database || dataSourceType === DataSourceType.File) && (
                <Steps activeStep={activeStep} setActiveStep={setActiveStep}>
                  <Steps.Step status={step1Status}>Connection</Steps.Step>
                  <Steps.Step status={step2Status} disabled={step1Status !== 'completed'}>
                    Data Selection
                  </Steps.Step>
                  <Steps.Step status={step3Status} disabled={step2Status !== 'completed'}>
                    Data Model
                  </Steps.Step>
                </Steps>
              )}
              {dataSourceType === DataSourceType.Import && (
                <Steps activeStep={activeStep} setActiveStep={setActiveStep}>
                  <Steps.Step status={step1Status} onClick={() => onResetImport()}>
                    File Upload
                  </Steps.Step>
                  <Steps.Step disabled status={step2Status}>
                    Connection
                  </Steps.Step>
                  <Steps.Step disabled status={step3Status}>
                    Data Model
                  </Steps.Step>
                </Steps>
              )}
            </Dialog.Bar>
            {isCreatePending ? (
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
