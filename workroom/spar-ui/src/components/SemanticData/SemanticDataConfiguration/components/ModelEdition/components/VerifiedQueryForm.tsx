import { useState, useEffect, useCallback, useRef, FC } from 'react';
import { Box, Input, Typography, Banner, useDebounce } from '@sema4ai/components';
import { IconInformation } from '@sema4ai/icons';
import { Code } from '../../../../../../common/code';

import { VerifiedQuery, SemanticModel, useVerifyVerifiedQueryMutation } from '../../../../../../queries/semanticData';

export type FormData = {
  name: string;
  nlq: string;
  sql: string;
};

type Props = {
  initialQuery?: VerifiedQuery;
  semanticDataModel: SemanticModel;
  verifyMutation: ReturnType<typeof useVerifyVerifiedQueryMutation>;
  onFormDataChange?: (data: FormData, isNonEmpty: boolean) => void;
  onValidationErrorsChange?: (errors: {
    sql_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    nlq_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    name_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
  }) => void;
  errors?: {
    sql_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    nlq_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
    name_errors?: Array<{ message: string; level: 'error' | 'warning' }>;
  };
  isNewQuery: boolean;
};

const getSingleError = (errorList?: Array<{ message: string; level: 'error' | 'warning' }>) => {
  if (!errorList || errorList.length === 0) return undefined;
  const found = errorList.find((error) => error.level === 'error');
  if (found) {
    return found.message;
  }
  return undefined;
};

export const VerifiedQueryForm: FC<Props> = ({
  initialQuery,
  semanticDataModel,
  verifyMutation,
  onFormDataChange,
  onValidationErrorsChange,
  errors: externalErrors,
  isNewQuery,
}) => {
  const [editedName, setEditedName] = useState(initialQuery?.name || '');
  const [editedNlq, setEditedNlq] = useState(initialQuery?.nlq || '');
  const [editedSql, setEditedSql] = useState(initialQuery?.sql || '');
  const initialValuesRef = useRef<{ name: string; nlq: string; sql: string } | null>(null);
  const previousInitialQueryRef = useRef<string>('');

  // Debounce the edited values for validation
  const debouncedName = useDebounce(editedName, 500);
  const debouncedNlq = useDebounce(editedNlq, 500);
  const debouncedSql = useDebounce(editedSql, 500);

  // Sync local state when initialQuery changes (only if content actually changed)
  useEffect(() => {
    if (initialQuery) {
      const initialName = initialQuery.name || '';
      const initialNlq = initialQuery.nlq || '';
      const initialSql = initialQuery.sql || '';

      // Create a stable key from the query content to detect actual changes
      const queryKey = `${initialName}|${initialNlq}|${initialSql}`;

      // Only update if the query content actually changed
      if (previousInitialQueryRef.current !== queryKey) {
        previousInitialQueryRef.current = queryKey;

        setEditedName(initialName);
        setEditedNlq(initialNlq);
        setEditedSql(initialSql);

        // Store initial values to detect user changes
        initialValuesRef.current = {
          name: initialName,
          nlq: initialNlq,
          sql: initialSql,
        };
      }
    } else if (previousInitialQueryRef.current !== '') {
      // Reset if initialQuery becomes undefined
      previousInitialQueryRef.current = '';
      initialValuesRef.current = null;
    }
  }, [initialQuery]);

  const isNonEmpty = editedName.trim().length > 0 && editedNlq.trim().length > 0 && editedSql.trim().length > 0;

  // Debounced validation when user makes changes
  useEffect(() => {
    // Only validate if all fields have content
    if (debouncedName.trim().length === 0 || debouncedNlq.trim().length === 0 || debouncedSql.trim().length === 0) {
      onValidationErrorsChange?.({});
      return;
    }

    // Perform validation
    const validateQuery = async () => {
      const queryToVerify: VerifiedQuery = {
        name: debouncedName.trim(),
        nlq: debouncedNlq.trim(),
        sql: debouncedSql.trim(),
        verified_at: initialQuery?.verified_at || '',
        verified_by: initialQuery?.verified_by || '',
      };

      try {
        const response = await verifyMutation.mutateAsync({
          semantic_data_model: semanticDataModel,
          verified_query: queryToVerify,
          accept_initial_name: isNewQuery ? '' : initialQuery?.name || '',
        });

        const verifiedQuery = response.verified_query;
        const validationErrors = {
          sql_errors: verifiedQuery.sql_errors,
          nlq_errors: verifiedQuery.nlq_errors,
          name_errors: verifiedQuery.name_errors,
        };
        onValidationErrorsChange?.(validationErrors);
      } catch (error) {
        // If validation fails, clear errors to avoid showing stale errors
        onValidationErrorsChange?.({});
      }
    };

    validateQuery();
  }, [debouncedName, debouncedNlq, debouncedSql, isNewQuery]);

  // Notify parent of form data changes
  useEffect(() => {
    onFormDataChange?.(
      {
        name: editedName,
        nlq: editedNlq,
        sql: editedSql,
      },
      isNonEmpty,
    );
  }, [editedName, editedNlq, editedSql, isNonEmpty, onFormDataChange]);

  const errors = externalErrors || {};

  const renderErrors = useCallback(
    (
      errorList: Array<{ message: string; level: 'error' | 'warning' }> | undefined,
      level: 'error' | 'warning' | 'all',
    ) => {
      if (!errorList || errorList.length === 0) return null;
      if (level !== 'all') {
        // eslint-disable-next-line no-param-reassign
        errorList = errorList.filter((error) => error.level === level);
      }
      return (
        <Box display="flex" flexDirection="column" gap="$4" mt="$4">
          {errorList.map((error, index) => (
            <Banner
              key={error.message ? `${error.level}:${error.message}:${index}` : `${error.level}:${index}`}
              message={error.message}
              variant={error.level === 'error' ? 'error' : 'alert'}
              icon={IconInformation}
            />
          ))}
        </Box>
      );
    },
    [],
  );

  return (
    <Box display="flex" flexDirection="column" gap="$16" py="$8">
      <Box display="flex" flexDirection="column" gap="$4">
        <Input
          label="Name"
          value={editedName}
          onChange={(e) => setEditedName(e.target.value)}
          placeholder=""
          description="Give the query a short and clear name."
          aria-label="Query name"
          error={getSingleError(errors.name_errors)}
        />
        {renderErrors(errors.name_errors, 'warning')}
      </Box>
      <Box display="flex" flexDirection="column" gap="$4">
        <Input
          label="Description"
          rows={3}
          value={editedNlq}
          onChange={(e) => setEditedNlq(e.target.value)}
          placeholder=""
          description="The query will be triggered when an agent receives a request matching the description."
          aria-label="Description"
          error={getSingleError(errors.nlq_errors)}
        />
        {renderErrors(errors.nlq_errors, 'warning')}
      </Box>
      <Box display="flex" flexDirection="column" gap="$4">
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Typography variant="body-medium" fontWeight="medium">
            Query
          </Typography>
        </Box>
        <Code value={editedSql} onChange={setEditedSql} title="SQL" rows={12} lang="sql" aria-label="SQL Query" />
        {renderErrors(errors.sql_errors, 'all')}
      </Box>
    </Box>
  );
};
