import { SemanticModel } from '../queries';

export const getTableDimensions = (table: SemanticModel['tables'][number]) => {
  return (table.dimensions || [])
    .concat(table.time_dimensions || [])
    .concat(table.facts || [])
    .concat(table.metrics || []);
};

export const parseSemanticModelErrors = (model: SemanticModel) => {
  const hasConnectionError = model.tables.some(
    (table) =>
      table.base_table.data_connection_id &&
      table.errors?.some((error) => error.level === 'error' && error.message.includes('Error accessing table')),
  );

  const hasFileReferenceWarning = model.tables.some(
    (table) =>
      table.base_table.file_reference &&
      table.errors?.some((error) => error.level === 'warning' && error.message.includes('unresolved file reference')),
  );

  const hasMissingTableReferenceError = model.tables.some((table) => {
    const dimensions = getTableDimensions(table);
    return dimensions.some((dimension) =>
      dimension.errors?.some(
        (error) =>
          error.level === 'error' && error.message.includes(`Column '${dimension.expr}' is not found in table`),
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
