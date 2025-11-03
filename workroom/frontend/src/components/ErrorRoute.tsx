import { FC, useMemo } from 'react';
import { Avatar, Box, Button, EmptyState, List, Typography } from '@sema4ai/components';
import { Link, ErrorComponentProps } from '@tanstack/react-router';

import errorIllustration from '~/assets/error.svg';
import { RequestError } from '~/lib/Error';
import { useTenantId } from '~/hooks/tenant';

export const ErrorRoute: FC<ErrorComponentProps> = ({ error }) => {
  const tenantId = useTenantId();

  const meta = useMemo((): { title: string; description: string; action: React.ReactElement } => {
    const defaultMeta = {
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

    if (!(error instanceof RequestError)) {
      return defaultMeta;
    }

    switch (error.status) {
      case 404: {
        if (!error.action) {
          return {
            title: `${error.message}`,
            description: 'The page you are looking for could not be found',
            action: (
              <Link to="/tenants/$tenantId" params={{ tenantId }}>
                <Button forwardedAs="span" round>
                  Return to Home
                </Button>
              </Link>
            ),
          };
        }

        error.action satisfies { type: 'tenants_selection' };

        return {
          title: `${error.message}`,
          description: `Either you don't have access to this workspace, or it doesn't exist.`,
          action: (
            <>
              <Typography textAlign="left" mb="$8" fontWeight="bold">
                Select a different workspace:
              </Typography>
              <Box mb="$16">
                <List>
                  {error.action.tenants.map(({ url, name }, idx) => (
                    <a href={url} key={idx}>
                      <List.Item icon={<Avatar placeholder={name} size="small" />}>{name}</List.Item>
                    </a>
                  ))}
                </List>
              </Box>
            </>
          ),
        };
      }
      case 401: {
        return {
          title: 'Authentication required',
          description: 'Your user could not be authenticated successfully.',
          action: (
            <Button onClick={() => window.location.reload()} round>
              Log in
            </Button>
          ),
        };
      }
      default:
        return defaultMeta;
    }
  }, [tenantId, error]);

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
