import { FC, useEffect, useMemo, useState } from 'react';
import { Dialog, Form, Progress, StepProps, Steps, useSnackbar } from '@sema4ai/components';
import { FormProvider, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useParams } from '@tanstack/react-router';
import { useConfirmAction } from '@sema4ai/layouts';

import {
  useCreateSemanticDataMutation,
  useSemanticModelQuery,
  useUpdateSemanticDataModelMutation,
  useImportSemanticDataModelMutation,
} from '~/queries/semanticData';
import { useDataConnectionDatabaseInspectMutation } from '~/queries/dataConnections';
import { useFeatureFlag, FeatureFlag } from '../../../hooks';

import {
  ConfigurationStep,
  DatabaseInspectionState,
  DataConnectionFormContext,
  DataConnectionFormSchema,
  DataSourceType,
  defaultFormDataValues,
  hasDataSelectionChanged,
  hasModelChanged,
  semanticModelToFormSchema,
  tablesToDataSelection,
} from './components/form';
import { DataConnection } from './components/DataConnection';
import { DataSelection } from './components/DataSelection';
import { ModelEdition } from './components/ModelEdition';
import { Processing } from './components/Processing';
import { SuccessView } from './components/SuccessView';
import { ImportWithErrors } from './components/ImportWithErrors';

type Props = {
  onClose: () => void;
  modelId?: string;
  initialStep?: ConfigurationStep;
};

export const SemanticDataConfiguration: FC<Props> = ({ onClose, modelId: initialModelId, initialStep }) => {
  const [modelId, setModelId] = useState<string | undefined>(initialModelId);
  const { agentId = '' } = useParams({ strict: false });
  const confirmCloseAction = useConfirmAction(
    {
      title: 'Are you sure?',
      text: 'Any unsaved changes will be lost.',
      confirmActionText: 'Discard changes',
      confirmButtonVariant: 'destructive',
    },
    [],
  );

  const initialStepValue = (() => {
    if (typeof initialStep === 'number') {
      return initialStep;
    }

    return initialModelId ? ConfigurationStep.ModelEdition : ConfigurationStep.DataConnection;
  })();

  const [activeStep, setActiveStep] = useState<ConfigurationStep>(initialStepValue);

  const { addSnackbar } = useSnackbar();
  const [databaseInspectionState, setDatabaseInspectionState] = useState<DatabaseInspectionState>({
    isLoading: false,
    error: undefined,
    inspectionResult: undefined,
    requiresInspection: false,
  });
  const [forceModelRegeneration, setForceModelRegeneration] = useState(false);
  const [dataSourceType, setDataSourceType] = useState<DataSourceType | undefined>(undefined);

  const { data: semanticModel, isLoading: isLoadingSemanticModel } = useSemanticModelQuery(
    { modelId: modelId || '' },
    { enabled: !!modelId },
  );

  const { mutate: createSemanticData, isPending: isCreatePending } = useCreateSemanticDataMutation({});
  const { mutate: updateSemanticData, isPending: isUpdatePending } = useUpdateSemanticDataModelMutation({});
  const { mutateAsync: inspectDataConnection } = useDataConnectionDatabaseInspectMutation({});
  const { mutateAsync: importSemanticDataModel } = useImportSemanticDataModelMutation({});
  const { enabled: canCreateAgents } = useFeatureFlag(FeatureFlag.canCreateAgents);

  const isPending = isCreatePending || isUpdatePending;

  const formMethods = useForm<DataConnectionFormSchema>({
    resolver: zodResolver(DataConnectionFormSchema),
    defaultValues: defaultFormDataValues,
  });

  const { dataSelection, tables, fileRefId, dataConnectionId } = formMethods.watch();

  useEffect(() => {
    if (semanticModel) {
      const values = semanticModelToFormSchema(semanticModel);
      formMethods.reset(values);

      if (values.dataConnectionId || values.dataConnectionName) {
        setDataSourceType(DataSourceType.Database);
      } else {
        setDataSourceType(DataSourceType.File);
      }
    }
  }, [semanticModel]);

  const onSubmit = formMethods.handleSubmit(async (values) => {
    if (modelId) {
      const shouldRegenerateModel = forceModelRegeneration || hasDataSelectionChanged(values);

      if (shouldRegenerateModel) {
        setActiveStep(ConfigurationStep.Processing);
      }

      updateSemanticData(
        { ...values, modelId, agentId, shouldRegenerateModel },
        {
          onSuccess: () => {
            addSnackbar({ message: 'Data model updated successfully', variant: 'success' });
            onClose();
          },
          onError: (error) => {
            addSnackbar({ message: error.message, variant: 'danger' });
          },
        },
      );
    } else if (dataSourceType === DataSourceType.Import) {
      setActiveStep(ConfigurationStep.Processing);
      await importSemanticDataModel(
        { ...values, agentId },
        {
          onSuccess: (result) => {
            if (result.withErrors) {
              setActiveStep(ConfigurationStep.ImportWithErrors);
            } else {
              setActiveStep(ConfigurationStep.SuccessImport);
            }

            setModelId(result.semanticModelId);
          },
          onError: (error) => {
            setActiveStep(ConfigurationStep.DataConnection);
            addSnackbar({ message: error.message, variant: 'danger' });
          },
        },
      );
    } else {
      setActiveStep(ConfigurationStep.Processing);
      createSemanticData(
        { ...values, agentId, inspectionResult: databaseInspectionState.inspectionResult },
        {
          onSuccess: (result) => {
            setActiveStep(ConfigurationStep.SuccessCreation);
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
    () => ({
      databaseInspectionState,
      setDatabaseInspectionState,
      onSubmit,
      forceModelRegeneration,
      setForceModelRegeneration,
    }),
    [databaseInspectionState, onSubmit, forceModelRegeneration],
  );

  useEffect(() => {
    const inspect = async () => {
      if (dataConnectionId) {
        setDatabaseInspectionState({
          isLoading: true,
          error: undefined,
          inspectionResult: undefined,
          requiresInspection: false,
        });

        await inspectDataConnection(
          { dataConnectionId, semanticModel },
          {
            onError: (error) => {
              setDatabaseInspectionState({
                isLoading: false,
                error: error.message,
                errorDetails: error.details.details,
                inspectionResult: undefined,
                requiresInspection: false,
              });
              if (!initialModelId) {
                setActiveStep(ConfigurationStep.DataConnection);
              }
            },
            onSuccess: (inspectionResult) => {
              if ('inspectionMismatches' in inspectionResult) {
                setDatabaseInspectionState({
                  isLoading: false,
                  error: 'The selected database is missing the tables or columns mapped in the imported data model.',
                  inspectionResult,
                  requiresInspection: false,
                });
              } else {
                setDatabaseInspectionState({
                  isLoading: false,
                  error: undefined,
                  inspectionResult,
                  requiresInspection: false,
                });
                if (!initialModelId) {
                  formMethods.setValue('dataSelection', tablesToDataSelection(inspectionResult, semanticModel));
                }
              }
            },
          },
        );
      }
    };
    inspect();
  }, [dataConnectionId, databaseInspectionState.requiresInspection]);

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

  const onCloseWithConfirmation = () => {
    if (activeStep === ConfigurationStep.SuccessCreation || activeStep === ConfigurationStep.SuccessImport) {
      onClose();
    } else if (activeStep === ConfigurationStep.DataConnection && !dataSourceType) {
      onClose();
    } else if (activeStep === ConfigurationStep.ModelEdition && semanticModel) {
      const hasModelChangedValue = hasModelChanged(formMethods.watch(), semanticModel);

      if (hasModelChangedValue) {
        confirmCloseAction(onClose)();
      } else {
        onClose();
      }
    } else {
      confirmCloseAction(onClose)();
    }
  };

  const onBackCallback = () => {
    switch (activeStep) {
      case ConfigurationStep.DataConnection:
        if (dataSourceType) {
          setDataSourceType(undefined);
          formMethods.reset(defaultFormDataValues);
        } else {
          onClose();
        }
        break;
      case ConfigurationStep.DataSelection:
        setActiveStep(ConfigurationStep.DataConnection);
        formMethods.reset(defaultFormDataValues);
        break;
      case ConfigurationStep.ModelEdition:
      default:
        onClose();
        break;
    }
  };

  const modelEditionStepProps: StepProps & { label: string } = (() => {
    return {
      status: modelId ? 'completed' : 'incomplete',
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
            {canCreateAgents &&
              activeStep !== ConfigurationStep.SuccessCreation &&
              activeStep !== ConfigurationStep.SuccessImport && (
                <Dialog.Bar onBackClick={onBackCallback}>
                  <Steps activeStep={activeStep} setActiveStep={setActiveStep}>
                    <Steps.Step {...connectionStepProps}>{connectionStepProps.label}</Steps.Step>
                    <Steps.Step {...dataSelectionStepProps}>{dataSelectionStepProps.label}</Steps.Step>
                    <Steps.Step {...modelEditionStepProps}>{modelEditionStepProps.label}</Steps.Step>
                  </Steps>
                </Dialog.Bar>
              )}
            {activeStep === ConfigurationStep.Processing && <Processing />}
            {activeStep === ConfigurationStep.ImportWithErrors && (
              <ImportWithErrors onClose={onCloseWithConfirmation} setActiveStep={setActiveStep} />
            )}
            {activeStep === ConfigurationStep.DataConnection && (
              <DataConnection
                onClose={onCloseWithConfirmation}
                setActiveStep={setActiveStep}
                setDataSourceType={setDataSourceType}
                dataSourceType={dataSourceType}
              />
            )}
            {activeStep === ConfigurationStep.DataSelection && (
              <DataSelection onClose={onCloseWithConfirmation} setActiveStep={setActiveStep} />
            )}
            {activeStep === ConfigurationStep.ModelEdition && modelId && (
              <ModelEdition onClose={onCloseWithConfirmation} setActiveStep={setActiveStep} modelId={modelId} />
            )}
            {(activeStep === ConfigurationStep.SuccessCreation || activeStep === ConfigurationStep.SuccessImport) && (
              <SuccessView
                onClose={onCloseWithConfirmation}
                setActiveStep={setActiveStep}
                modelName={semanticModel?.name}
                currentStep={activeStep}
              />
            )}
          </DataConnectionFormContext.Provider>
        </FormProvider>
      </Form>
    </Dialog>
  );
};
