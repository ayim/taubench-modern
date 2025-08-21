import { Typography } from '@sema4ai/components';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/tenants/$tenantId/help/')({
  component: () => (
    <Typography fontSize="$28" fontWeight="medium">
      Help
    </Typography>
  ),
});
