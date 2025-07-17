import { Box, Button, EmptyState } from '@sema4ai/components';
import { Link } from '@tanstack/react-router';

import errorIllustration from '~/assets/error.svg';

export const AgentNotFound = () => {
  return (
    <Box display="flex" justifyContent="center" flexDirection="column" maxHeight={960} height="100%">
      <EmptyState
        illustration={<img src={errorIllustration} loading="lazy" alt="" />}
        title="Agent not found"
        description="The Agent you are looking for was not found"
        action={
          <Link to="/">
            <Button forwardedAs="span" round>
              Return to Home
            </Button>
          </Link>
        }
      />
    </Box>
  );
};
