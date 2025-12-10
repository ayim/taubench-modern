import { FC, useMemo } from 'react';
import { Avatar, Box, Button, EmptyState, List, Typography } from '@sema4ai/components';
import { Link, ErrorComponentProps } from '@tanstack/react-router';
import { TRPCClientError } from '@trpc/client';

import errorIllustration from '~/assets/error.svg';
import { RequestError } from '~/lib/Error';
import { useTenantId } from '~/hooks/tenant';
import { InferrableClientTypes } from '@trpc/server/unstable-core-do-not-import';

type ExpectedError = RequestError | TRPCClientError<InferrableClientTypes> | Error;

type ParsedExpectedError = {
  httpStatus: number | null;
  errorMessage: string;
  errorAction: RequestError['action'] | undefined;
};

const parseError = (error: ExpectedError): ParsedExpectedError => {
  if (error instanceof RequestError) {
    return {
      httpStatus: error.status,
      errorMessage: error.message,
      errorAction: error.action,
    };
  }
  if (error instanceof TRPCClientError) {
    return {
      httpStatus: error.data?.httpStatus ?? null,
      errorMessage: error.message,
      errorAction: undefined,
    };
  }
  return {
    httpStatus: null,
    errorMessage: error.message,
    errorAction: undefined,
  };
};

export const ErrorRoute: FC<ErrorComponentProps<ExpectedError>> = ({ error }) => {
  const tenantId = useTenantId();

  const meta = useMemo((): { title: string; description: string; action: React.ReactElement } => {
    const { httpStatus, errorMessage, errorAction } = parseError(error);

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

    if (httpStatus === null) {
      return defaultMeta;
    }

    switch (httpStatus) {
      case 404: {
        if (!errorAction) {
          return {
            title: errorMessage,
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

        errorAction satisfies { type: 'tenants_selection' };

        return {
          title: errorMessage,
          description: `Either you don't have access to this workspace, or it doesn't exist.`,
          action: (
            <>
              <Typography textAlign="left" mb="$8" fontWeight="bold">
                Select a different workspace:
              </Typography>
              <Box mb="$16">
                <List>
                  {errorAction.tenants.map(({ url, name }, idx) => (
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
      case 403: {
        return {
          title: 'Access forbidden',
          description: `You do not have the necessary permissions: ${errorMessage}`,
          action: (
            <Link to="/tenants/$tenantId" params={{ tenantId }}>
              <Button forwardedAs="span" round>
                Return to Home
              </Button>
            </Link>
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
