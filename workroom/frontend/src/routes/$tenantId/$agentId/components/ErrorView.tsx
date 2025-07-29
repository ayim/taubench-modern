import { Link } from '@tanstack/react-router';

import { Box, Button, EmptyState } from '@sema4ai/components';
import errorIllustration from '~/assets/error.svg';

export interface PageNotFoundErrorDetails {
  title: string;
  description: string;
}

/**
 * Show this when some thread / workitem / dashboard is not available.
 * May be because it was deleted or id is wrong
 */
export default function ErrorView({ title, description }: PageNotFoundErrorDetails) {
  return (
    <Box display="flex" justifyContent="center" flexDirection="column" height="calc(100% - 72px)">
      <EmptyState
        illustration={<img src={errorIllustration} loading="lazy" alt="" />}
        title={title}
        description={description}
        action={
          <Link to="/$tenantId/$agentId" from="/$tenantId/$agentId">
            <Button forwardedAs="span" round>
              Return to Agent
            </Button>
          </Link>
        }
      />
    </Box>
  );
}
