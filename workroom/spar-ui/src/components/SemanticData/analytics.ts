import { useAnalytics } from '../../queries/analytics';
import { useAgentQuery } from '../../queries/agents';
import { useDataConnectionQuery } from '../../queries/dataConnections';
import { AnalyticsEvent } from '../../api';
import { DataSourceType } from './SemanticDataConfiguration/components/form';

/**
 * Helper function to determine the dialect based on data source type
 */
const getDialect = (
  dataSourceType: DataSourceType | undefined,
  fileRefId?: string,
  dataConnectionEngine?: string,
): string => {
  if (dataSourceType === DataSourceType.File && fileRefId) {
    const ext = fileRefId.toLowerCase().split('.').pop();
    if (ext === 'csv') return 'csv';
    if (ext === 'xls' || ext === 'xlsx') return 'excel';
    return 'unknown';
  }

  if (dataSourceType === DataSourceType.Database && dataConnectionEngine) {
    return dataConnectionEngine;
  }

  return 'unknown';
};

/**
 * Custom hook for Semantic Data Model analytics tracking
 * Centralizes all SDM-specific telemetry logic
 */
export const useSemanticDataAnalytics = (params: {
  agentId: string;
  dataSourceType?: DataSourceType;
  dataConnectionId?: string;
  fileRefId?: string;
}) => {
  const { track } = useAnalytics();
  const { data: agent } = useAgentQuery({ agentId: params.agentId });
  const { data: dataConnection } = useDataConnectionQuery(
    { dataConnectionId: params.dataConnectionId || '' },
    { enabled: !!params.dataConnectionId },
  );

  const trackSemanticDataModelCreated = (success: boolean) => {
    const agentName = agent?.name || 'unknown';
    const type = params.dataSourceType === DataSourceType.File ? 'file' : 'database';
    const dialect = getDialect(params.dataSourceType, params.fileRefId, dataConnection?.engine);

    track(
      `semantic_data_model.created.${agentName}.${type}.${dialect}` as AnalyticsEvent,
      success ? 'success' : 'failed',
    );
  };

  const trackSemanticDataModelImported = (success: boolean) => {
    const agentName = agent?.name || 'unknown';
    const type = params.dataSourceType === DataSourceType.File ? 'file' : 'database';
    const dialect = getDialect(params.dataSourceType, params.fileRefId, dataConnection?.engine);

    track(
      `semantic_data_model.imported.${agentName}.${type}.${dialect}` as AnalyticsEvent,
      success ? 'success' : 'failed',
    );
  };

  const trackSemanticDataModelModified = () => {
    track('semantic_data_model.modified' as AnalyticsEvent);
  };

  const trackSemanticDataModelDeleted = () => {
    track('semantic_data_model.deleted' as AnalyticsEvent);
  };

  const trackVerifiedQueryCreated = (success: boolean) => {
    const agentName = agent?.name || 'unknown';
    const type = params.dataSourceType === DataSourceType.File ? 'file' : 'database';
    const dialect = getDialect(params.dataSourceType, params.fileRefId, dataConnection?.engine);

    track(
      `semantic_data_model.verified_query.created.${agentName}.${type}.${dialect}` as AnalyticsEvent,
      success ? 'success' : 'failed',
    );
  };

  const trackVerifiedQueryModified = () => {
    track('semantic_data_model.verified_query.modified' as AnalyticsEvent);
  };

  const trackVerifiedQueryDeleted = () => {
    track('semantic_data_model.verified_query.deleted' as AnalyticsEvent);
  };

  return {
    trackSemanticDataModelCreated,
    trackSemanticDataModelImported,
    trackSemanticDataModelModified,
    trackSemanticDataModelDeleted,
    trackVerifiedQueryCreated,
    trackVerifiedQueryModified,
    trackVerifiedQueryDeleted,
  };
};
