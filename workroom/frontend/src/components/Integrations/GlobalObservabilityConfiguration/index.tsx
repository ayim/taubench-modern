import { Progress } from '@sema4ai/components';
import { useObservabilityIntegrationsQuery } from '~/queries/integrations';
import { CreateObservabilityIntegration } from '../components/CreateObservabilityIntegration';
import { UpdateObservabilityIntegration } from '../components/UpdateObservabilityIntegration';

export const GlobalObservabilityConfiguration = () => {
  const { data: observabilityIntegrations, isFetching, isRefetching } = useObservabilityIntegrationsQuery({});

  /**
   * We only want to show the Progress on initial load - refetching should happen in the background.
   * Apart from ensuring better UX, it ensures that the UpdateObservabilityIntegration form value do not get
   * reset when refetch finishes and component mounts again, potentially overwriting user changes (that could
   * happen when user navigates away from the page to other tab browser and back).
   */
  if (isFetching && !isRefetching) {
    return <Progress variant="default" />;
  }

  if (observabilityIntegrations && observabilityIntegrations.length > 1) {
    // eslint-disable-next-line no-console
    console.warn(`Detected ${observabilityIntegrations.length} integrations, only displaying the first one`);
  }

  /**
   * This view is only concerned with a single, global ObservabilityIntegration.
   */
  const globalObservabilityIntegration = observabilityIntegrations?.[0];

  if (globalObservabilityIntegration) {
    return <UpdateObservabilityIntegration integrationId={globalObservabilityIntegration.id} />;
  }

  return <CreateObservabilityIntegration />;
};
