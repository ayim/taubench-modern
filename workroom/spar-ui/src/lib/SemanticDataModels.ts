import { SemanticDataValidationErrorKind, SemanticModel } from '../queries';

export const getTableDimensions = (table: SemanticModel['tables'][number]) => {
  return (table.dimensions || [])
    .concat(table.time_dimensions || [])
    .concat(table.facts || [])
    .concat(table.metrics || []);
};

export const parseSemanticModelErrors = (model: SemanticModel) => {
  const hasModelConnectionError = model.errors?.some((error) =>
    [
      SemanticDataValidationErrorKind.data_connection_connection_failed,
      SemanticDataValidationErrorKind.data_connection_table_access_error,
      SemanticDataValidationErrorKind.data_connection_not_found,
      SemanticDataValidationErrorKind.missing_data_connection,
    ].includes(error.kind),
  );

  const hasTableConnectionError = model.tables.some((table) =>
    table.errors?.some((error) =>
      [
        SemanticDataValidationErrorKind.data_connection_connection_failed,
        SemanticDataValidationErrorKind.data_connection_table_access_error,
        SemanticDataValidationErrorKind.data_connection_not_found,
        SemanticDataValidationErrorKind.missing_data_connection,
      ].includes(error.kind),
    ),
  );

  const hasConnectionError = hasModelConnectionError || hasTableConnectionError;

  const hasFileReferenceWarning = model.tables.some((table) =>
    table.errors?.some((error) =>
      [
        SemanticDataValidationErrorKind.file_not_found,
        SemanticDataValidationErrorKind.file_reference_unresolved,
      ].includes(error.kind),
    ),
  );

  const hasMissingTableReferenceError = model.tables.some((table) => {
    const hasMissingTables = table.errors?.some((error) =>
      [
        SemanticDataValidationErrorKind.semantic_model_duplicate_table,
        SemanticDataValidationErrorKind.data_connection_table_not_found,
      ].includes(error.kind),
    );

    if (hasMissingTables) {
      return true;
    }

    const dimensions = getTableDimensions(table);
    return dimensions.some((dimension) =>
      dimension.errors?.some((error) =>
        [
          SemanticDataValidationErrorKind.semantic_model_missing_required_field,
          SemanticDataValidationErrorKind.data_connection_column_invalid_expression,
        ].includes(error.kind),
      ),
    );
  });

  return {
    hasConnectionError,
    hasFileReferenceWarning,
    hasMissingTableReferenceError,
  };
};

export const requiresDataConnection = (semanticModel: SemanticModel): boolean => {
  return semanticModel.tables.some(
    (table) => !!table.base_table.data_connection_id || !!table.base_table.data_connection_name,
  );
};

/**
 * Get the data connection ID from the first table with a data connection ID.
 * @param semanticModel
 * @returns The data connection ID from the first table with a data connection ID, or undefined if no table has a data connection ID.
 */
export const getDataConnectionId = (semanticModel: SemanticModel): string | undefined => {
  return semanticModel.tables.find((table) => table.base_table?.data_connection_id)?.base_table?.data_connection_id;
};
