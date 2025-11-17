import { Progress } from '@sema4ai/components';
import { useObservabilityIntegrationsQuery } from '../../../queries';
import { CreateObservabilityIntegration } from '../components/CreateObservabilityIntegration';
import { UpdateObservabilityIntegration } from '../components/UpdateObservabilityIntegration';

export const GlobalObservabilityConfiguration = () => {
  const { data: observabilityIntegrations, isFetching } = useObservabilityIntegrationsQuery({});

  if (isFetching) {
    return <Progress variant="default" />;
  }

  if (observabilityIntegrations && observabilityIntegrations.length > 1) {
    // eslint-disable-next-line no-console
    console.warn(`Detected ${observabilityIntegrations.length} integrations, only displaying the first one`);
  }

  /**
   * This view is only concerned with a single, global ObservabilityIntegration. For now, it's only a Studio
   * use case - Workroom and Control Room will most likely allow to configure multiple integrations. Such case
   * will need to be handle by a separate list view.
   */
  const globalObservabilityIntegration = observabilityIntegrations?.[0];

  if (globalObservabilityIntegration) {
    return <UpdateObservabilityIntegration integrationId={globalObservabilityIntegration.id} />;
  }

  return <CreateObservabilityIntegration />;
};
