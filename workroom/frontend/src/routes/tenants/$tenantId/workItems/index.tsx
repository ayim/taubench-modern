import { createFileRoute, redirect } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/workItems/')({
  loader: ({ params }) => {
    throw redirect({
      to: '/tenants/$tenantId/workItems/overview',
      params,
    });
  },
});
