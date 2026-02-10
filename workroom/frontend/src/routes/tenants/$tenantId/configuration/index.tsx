import { createFileRoute, redirect } from '@tanstack/react-router';
import { shouldDisplayConfigurationSidebarLink } from '~/lib/tenantContext';

export const Route = createFileRoute('/tenants/$tenantId/configuration/')({
  loader: async ({ params, context: { trpc: trpcClient } }) => {
    const tenantConfig = await trpcClient.configuration.getTenantConfig.ensureData();

    if (!shouldDisplayConfigurationSidebarLink({ features: tenantConfig.features })) {
      return;
    }

    const shouldRedirectToLLMs = tenantConfig.features.deploymentWizard.enabled;

    if (shouldRedirectToLLMs) {
      throw redirect({
        to: '/tenants/$tenantId/configuration/llm',
        params,
      });
    }

    const shouldRedirectToSettings = tenantConfig.features.settings.enabled;

    if (shouldRedirectToSettings) {
      throw redirect({
        to: '/tenants/$tenantId/configuration/settings',
        params,
      });
    }
  },
});
