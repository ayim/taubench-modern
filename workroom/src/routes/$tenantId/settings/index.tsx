import { Typography } from '@sema4ai/components';
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/$tenantId/settings/')({
  component: () => (
    <Typography fontSize="$28" fontWeight="medium">
      Settings
    </Typography>
  ),
});
