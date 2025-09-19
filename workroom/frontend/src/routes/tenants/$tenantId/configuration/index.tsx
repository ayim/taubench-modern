import { createFileRoute, redirect } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/configuration/')({
  loader: async ({ params }) => {
    throw redirect({
      to: '/tenants/$tenantId/configuration/llm',
      params,
    });
  },
});
