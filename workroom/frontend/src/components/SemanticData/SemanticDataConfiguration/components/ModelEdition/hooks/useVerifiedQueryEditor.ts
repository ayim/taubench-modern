import { useCallback, useRef, useState } from 'react';
import { useFormContext } from 'react-hook-form';
import { useDeleteConfirm } from '@sema4ai/layouts';

import { VerifiedQuery, SemanticModel, useVerifyVerifiedQueryMutation } from '~/queries/semanticData';
import { DataConnectionFormSchema } from '../../form';
import { FormData as VerifiedQueryFormData } from '../components/VerifiedQueryForm';

type VerificationErrors = {
  sql_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
  nlq_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
  name_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
  parameter_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
};

type UseVerifiedQueryEditorOptions = {
  index: number | undefined;
  modelId: string;
  onDone: () => void;
};

const filterErrors = (
  errorList?: Array<{ message: string; level: 'error' | 'warning' }>,
  level: 'error' | 'warning' = 'error',
): Array<{ message: string; level: 'error' | 'warning' }> => {
  if (!errorList || errorList.length === 0) return [];
  return errorList.filter((error) => error.level === level);
};

export const useVerifiedQueryEditor = ({ index, modelId, onDone }: UseVerifiedQueryEditorOptions) => {
  const { watch, setValue } = useFormContext<DataConnectionFormSchema>();

  const formDataRef = useRef<VerifiedQueryFormData | null>(null);
  const [isFormValid, setIsFormValid] = useState(false);
  const [errors, setErrors] = useState<VerificationErrors>({});
  const verifyMutation = useVerifyVerifiedQueryMutation({});

  const { name, description, tables, verifiedQueries } = watch();
  const currentQueries = verifiedQueries || [];

  const isEditing = index !== undefined;
  const editingQuery: VerifiedQuery | undefined = isEditing ? currentQueries[index] : undefined;

  const semanticDataModel: SemanticModel = {
    id: modelId,
    name: name || '',
    description: description || '',
    tables: tables || [],
    verified_queries: currentQueries,
  };

  const handleFormDataChange = useCallback((data: VerifiedQueryFormData, isNonEmpty: boolean) => {
    formDataRef.current = data;
    setIsFormValid(isNonEmpty);
  }, []);

  const handleValidationErrorsChange = useCallback((validationErrors: VerificationErrors) => {
    setErrors(validationErrors);
  }, []);

  const handleSave = useCallback(async () => {
    const formData = formDataRef.current;
    if (!formData) return;

    const originalQuery = index !== undefined ? currentQueries[index] : undefined;

    const queryToVerify: VerifiedQuery = {
      name: formData.name.trim(),
      nlq: formData.nlq.trim(),
      sql: formData.sql.trim(),
      verified_at: originalQuery?.verified_at || '',
      verified_by: originalQuery?.verified_by || '',
      parameters: formData.parameters,
    };

    const response = await verifyMutation.mutateAsync({
      semantic_data_model: semanticDataModel,
      verified_query: queryToVerify,
      accept_initial_name: originalQuery?.name || '',
    });

    const verifiedQuery = response.verified_query;

    const hasErrors =
      filterErrors(verifiedQuery.sql_errors, 'error').length > 0 ||
      filterErrors(verifiedQuery.nlq_errors, 'error').length > 0 ||
      filterErrors(verifiedQuery.name_errors, 'error').length > 0 ||
      filterErrors(verifiedQuery.parameter_errors, 'error').length > 0;

    if (hasErrors) {
      setErrors({
        sql_errors: verifiedQuery.sql_errors,
        nlq_errors: verifiedQuery.nlq_errors,
        name_errors: verifiedQuery.name_errors,
        parameter_errors: verifiedQuery.parameter_errors,
      });
      return;
    }

    const newQuery: VerifiedQuery = {
      ...queryToVerify,
      name: verifiedQuery.name,
      nlq: verifiedQuery.nlq,
      sql: verifiedQuery.sql,
      verified_at: verifiedQuery.verified_at,
      verified_by: verifiedQuery.verified_by,
      parameters: verifiedQuery.parameters || queryToVerify.parameters,
      result_type: verifiedQuery.result_type,
    };

    if (index !== undefined) {
      const updatedQueries = [...currentQueries];
      updatedQueries[index] = {
        ...originalQuery!,
        ...newQuery,
      };
      setValue('verifiedQueries', updatedQueries);
    } else {
      setValue('verifiedQueries', [...currentQueries, newQuery]);
    }
    onDone();
  }, [currentQueries, index, verifyMutation, semanticDataModel, setValue, onDone]);

  const onDeleteConfirm = useDeleteConfirm(
    {
      entityName: editingQuery?.name,
      entityType: 'verified query',
    },
    [editingQuery?.name],
  );

  const handleDelete = onDeleteConfirm(() => {
    if (index !== undefined) {
      const updatedQueries = currentQueries.filter((_, i) => i !== index);
      setValue('verifiedQueries', updatedQueries);
      onDone();
    }
  });

  const handleBack = useCallback(() => {
    setErrors({});
    onDone();
  }, [onDone]);

  return {
    editingQuery,
    handleFormDataChange,
    handleValidationErrorsChange,
    verifiedQueryErrors: errors,
    verifyMutation,
    semanticDataModel,
    editorProps: {
      breadcrumb: 'Verified Queries',
      title: isEditing ? 'Edit Verified Query' : 'Create Verified Query',
      saveLabel: isEditing ? 'Save' : 'Create',
      isSaveDisabled: !isFormValid || verifyMutation.isPending,
      isSaving: verifyMutation.isPending,
      isEditing,
      onSave: handleSave,
      onDelete: handleDelete,
      onBack: handleBack,
    },
  };
};
