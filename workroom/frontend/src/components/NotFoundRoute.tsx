import { Box, Button, EmptyState } from '@sema4ai/components';
import { Link } from '@tanstack/react-router';

import errorIllustration from '~/assets/error.svg';
import { useTenantId } from '~/hooks/tenant';

export const NotFoundRoute = () => {
  const tenantId = useTenantId();

  return (
    <Box display="flex" justifyContent="center" flexDirection="column" maxHeight={960} height="100%">
      <EmptyState
        illustration={<img src={errorIllustration} loading="lazy" alt="" />}
        title="Page not found"
        description="The page you are looking for was not found"
        action={
          <Link to="/tenants/$tenantId" params={{ tenantId }}>
            <Button forwardedAs="span" round>
              Return to Home
            </Button>
          </Link>
        }
      />
    </Box>
  );
};
