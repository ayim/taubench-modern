import { FC } from 'react';
import { Box, Button, EmptyState } from '@sema4ai/components';
import { Link, ErrorComponentProps } from '@tanstack/react-router';

import errorIllustration from '~/assets/error.svg';
import { RequestError } from '~/lib/Error';
import { useTenantId } from '~/hooks/tenant';

export const ErrorRoute: FC<ErrorComponentProps> = ({ error }) => {
  const tenantId = useTenantId();

  let meta = {
    title: 'An error happened',
    description: 'An unknown error occured.',
    action: (
      <Link to="/tenants/$tenantId" params={{ tenantId }}>
        <Button forwardedAs="span" round>
          Return to Home
        </Button>
      </Link>
    ),
  };

  if (error instanceof RequestError) {
    if (error.status === 404) {
      meta = {
        ...meta,
        title: `${error.message}`,
        description: 'The page You are looking for could not be found',
      };
    }
    if (error.status === 401) {
      meta = {
        ...meta,
        title: 'Authentication required',
        description: 'Your user could not be authenticated successfully.',
        action: (
          <Button onClick={() => window.location.reload()} round>
            Log in
          </Button>
        ),
      };
    }
  }

  return (
    <Box
      as="section"
      display="flex"
      justifyContent="center"
      flexDirection="column"
      maxHeight={960}
      height="calc(100% - 72px)"
    >
      <EmptyState
        illustration={<img src={errorIllustration} loading="lazy" alt="" />}
        title={meta.title}
        description={meta.description}
        action={meta.action}
      />
    </Box>
  );
};
