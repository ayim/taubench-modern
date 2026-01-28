import { FC, useState, useCallback, useEffect } from 'react';
import { Button, Dialog, Link } from '@sema4ai/components';
import { useFormContext } from 'react-hook-form';
import { useDeleteConfirm } from '@sema4ai/layouts';

import { DataConnectionFormSchema } from '../../form';
import { VerifiedQuery, useVerifyVerifiedQueryMutation, SemanticModel } from '~/queries/semanticData';
import { EXTERNAL_LINKS } from '../../../../../../lib/constants';
import { VerifiedQueryForm, FormData } from './VerifiedQueryForm';

type Props = {
  open: boolean;
  onClose: () => void;
  queryIndex?: number;
  query?: VerifiedQuery;
  modelId: string;
};

const filterErrors = (
  errorList?: Array<{ message: string; level: 'error' | 'warning' }>,
  level: 'error' | 'warning' = 'error',
) => {
  if (!errorList || errorList.length === 0) return [];
  return errorList.filter((error) => error.level === level);
};

export const EditVerifiedQueryDialog: FC<Props> = ({ open, onClose, queryIndex, query, modelId }) => {
  const { setValue, watch } = useFormContext<DataConnectionFormSchema>();
  const onDeleteConfirm = useDeleteConfirm(
    {
      entityName: query?.name,
      entityType: 'verified query',
    },
    [],
  );

  const isEditMode = queryIndex !== undefined && query !== undefined;
  const [formData, setFormData] = useState<FormData>({
    name: query?.name || '',
    nlq: query?.nlq || '',
    sql: query?.sql || '',
    parameters: query?.parameters || [],
  });
  const [isFormValid, setIsFormValid] = useState(false);
  const [errors, setErrors] = useState<{
    sql_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    nlq_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    name_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    parameter_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
  }>({});
  const verifyMutation = useVerifyVerifiedQueryMutation({});

  const verifiedQueries = watch('verifiedQueries') || [];
  const tables = watch('tables') || [];
  const [name, description] = watch(['name', 'description', 'dataConnectionId', 'fileRefId']);

  // Build semantic data model from form data
  const semanticDataModel: SemanticModel = {
    id: modelId,
    name: name || '',
    description: description || '',
    tables,
    verified_queries: verifiedQueries,
  };

  // Reset errors when dialog opens
  useEffect(() => {
    if (open) {
      setErrors({});
    }
  }, [open]);

  const handleSave = useCallback(async () => {
    const queryToVerify: VerifiedQuery = {
      name: formData.name.trim(),
      nlq: formData.nlq.trim(),
      sql: formData.sql.trim(),
      verified_at: query?.verified_at || '',
      verified_by: query?.verified_by || '',
      parameters: formData.parameters,
    };

    // Verify the query
    const response = await verifyMutation.mutateAsync({
      semantic_data_model: semanticDataModel,
      verified_query: queryToVerify,
      accept_initial_name: query?.name || '',
    });

    const verifiedQuery = response.verified_query;

    // Check if there are any errors
    const hasErrors =
      filterErrors(verifiedQuery.sql_errors, 'error').length > 0 ||
      filterErrors(verifiedQuery.nlq_errors, 'error').length > 0 ||
      filterErrors(verifiedQuery.name_errors, 'error').length > 0 ||
      filterErrors(verifiedQuery.parameter_errors, 'error').length > 0;

    if (hasErrors) {
      // Show errors but don't save
      setErrors({
        sql_errors: verifiedQuery.sql_errors,
        nlq_errors: verifiedQuery.nlq_errors,
        name_errors: verifiedQuery.name_errors,
        parameter_errors: verifiedQuery.parameter_errors,
      });
      return;
    }

    // No errors, save the verified query with verified_at and verified_by from response
    const newQuery: VerifiedQuery = {
      ...queryToVerify,
      name: verifiedQuery.name,
      nlq: verifiedQuery.nlq,
      sql: verifiedQuery.sql,
      verified_at: verifiedQuery.verified_at,
      verified_by: verifiedQuery.verified_by,
      parameters: verifiedQuery.parameters || queryToVerify.parameters,
    };

    if (isEditMode && queryIndex !== undefined) {
      // Update existing query
      const updatedQueries = [...verifiedQueries];
      updatedQueries[queryIndex] = {
        ...query!,
        ...newQuery,
      };
      setValue('verifiedQueries', updatedQueries);
    } else {
      // Create new query
      setValue('verifiedQueries', [...verifiedQueries, newQuery]);
    }
    onClose();
  }, [formData, isEditMode, queryIndex, query, verifiedQueries, setValue, onClose, semanticDataModel]);

  const handleClose = useCallback(() => {
    setErrors({});
    onClose();
  }, [onClose]);

  const handleFormDataChange = useCallback((data: FormData, isNonEmpty: boolean) => {
    setFormData(data);
    setIsFormValid(isNonEmpty);
  }, []);

  const handleValidationErrorsChange = useCallback(
    (validationErrors: {
      sql_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
      nlq_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
      name_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    }) => {
      setErrors(validationErrors);
    },
    [],
  );

  const handleDelete = onDeleteConfirm(() => {
    const updatedQueries = verifiedQueries.filter((_, i) => i !== queryIndex);
    setValue('verifiedQueries', updatedQueries);
    onClose();
  });

  return (
    <Dialog open={open} onClose={handleClose} size="x-large">
      <Dialog.Header>
        <Dialog.Header.Title title={isEditMode ? 'Edit Verified Query' : 'Create Verified Query'} />
        <Dialog.Header.Description>
          Verified queries let you save and reuse queries that you&apos;ve confirmed to be accurate. We have
          automatically identified the potential parameters that the agent can change in your query.{' '}
          <Link href={EXTERNAL_LINKS.NAMED_QUERIES} target="_blank">
            Learn more
          </Link>
        </Dialog.Header.Description>
      </Dialog.Header>
      <Dialog.Content>
        <VerifiedQueryForm
          isNewQuery={!isEditMode}
          initialQuery={query}
          semanticDataModel={semanticDataModel}
          verifyMutation={verifyMutation}
          onFormDataChange={handleFormDataChange}
          onValidationErrorsChange={handleValidationErrorsChange}
          errors={errors}
        />
      </Dialog.Content>
      <Dialog.Actions>
        <Button
          variant="primary"
          onClick={handleSave}
          disabled={!isFormValid || verifyMutation.isPending}
          loading={verifyMutation.isPending}
          round
        >
          {isEditMode ? 'Save' : 'Create'}
        </Button>
        <Button variant="secondary" onClick={handleClose} round>
          Cancel
        </Button>
        {isEditMode && (
          <Button variant="secondary" onClick={handleDelete} align="secondary" round>
            Delete
          </Button>
        )}
      </Dialog.Actions>
    </Dialog>
  );
};
