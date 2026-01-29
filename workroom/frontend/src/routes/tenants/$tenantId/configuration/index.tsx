import { createFileRoute, redirect } from '@tanstack/react-router';
import { shouldDisplayConfigurationSidebarLink } from '~/lib/tenantContext';

export const Route = createFileRoute('/tenants/$tenantId/configuration/')({
  loader: async ({ params, context: { agentAPIClient } }) => {
    const tenantMeta = await agentAPIClient.getTenantMeta();

    if (!tenantMeta) {
      // No-op: the configuration view is only surfacing feature-gated views
      return;
    }

    if (!shouldDisplayConfigurationSidebarLink({ features: tenantMeta.features })) {
      // No-op: direct access via URL leads to this
      return;
    }

    const shouldRedirectToLLMs = tenantMeta?.features.deploymentWizard.enabled;

    if (shouldRedirectToLLMs) {
      throw redirect({
        to: '/tenants/$tenantId/configuration/llm',
        params,
      });
    }

    const shouldRedirectToSettings = tenantMeta?.features.settings.enabled;

    if (shouldRedirectToSettings) {
      throw redirect({
        to: '/tenants/$tenantId/configuration/settings',
        params,
      });
    }
  },
});
