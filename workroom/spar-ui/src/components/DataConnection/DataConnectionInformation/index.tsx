import { FC, ReactNode, useMemo, useState } from 'react';
import { Box, Button, PopoverProps, Typography, usePopover } from '@sema4ai/components';
import { IconStatusDisabled, IconStatusError } from '@sema4ai/icons';

import { useDataConnectionQuery } from '../../../queries';
import { getGeneralDataConnectionDetails } from '../../../lib/DataConnections';
import { snakeCaseToCamelCase } from '../../../lib/utils';
import { useFeatureFlag } from '../../../hooks';
import { SparUIFeatureFlag } from '../../../api';
import { UpdateDataConnection } from '../DataConnectionConfiguration/components/Update';

type Props = {
  dataConnectionId?: string;
  children: ReactNode;
  placement?: PopoverProps['placement'];
  error?: {
    level: 'error' | 'warning';
    title: string;
    description: string;
  };
  action?: ReactNode;
  onDataConnectionUpdate?: () => void;
};

export const DataConnectionInformation: FC<Props> = ({
  action,
  dataConnectionId,
  error,
  children,
  placement,
  onDataConnectionUpdate,
}) => {
  const [isUpdateConnectionOpen, setIsUpdateConnectionOpen] = useState(false);

  const onCloseUpdateConnection = () => {
    onDataConnectionUpdate?.();
    setIsUpdateConnectionOpen(false);
  };

  const { data: dataConnection } = useDataConnectionQuery(
    {
      dataConnectionId: dataConnectionId || '',
    },
    {
      enabled: !!dataConnectionId,
    },
  );
  const { referenceRef, referenceProps, PopoverContent, setOpen } = usePopover({
    hover: true,
    delay: 200,
    placement,
  });

  const onPopoverClick = () => {
    setOpen(false);
  };

  const dataConnectionDetails = useMemo(() => {
    return dataConnection ? Object.entries(getGeneralDataConnectionDetails(dataConnection)) : null;
  }, [dataConnection]);

  const { enabled: canCreateAgents } = useFeatureFlag(SparUIFeatureFlag.canCreateAgents);

  const ErrorIcon = error?.level === 'error' ? IconStatusError : IconStatusDisabled;
  const errorIconColor = error?.level === 'error' ? 'content.error' : 'background.notification';

  return (
    <>
      <Box ref={referenceRef} {...referenceProps}>
        {children}
      </Box>
      <PopoverContent>
        {(dataConnection || error) && (
          <Box
            display="flex"
            flexDirection="column"
            gap="$12"
            width={280}
            p="$16"
            borderRadius="$8"
            boxShadow="medium"
            backgroundColor="background.panels"
            onClick={onPopoverClick}
          >
            {error && (
              <>
                <Box display="flex" alignItems="center" gap="$8">
                  <ErrorIcon color={errorIconColor} />
                  <Typography variant="body-large" fontWeight="medium">
                    {error.title}
                  </Typography>
                </Box>
                <Typography color="content.subtle.light" pb="$12">
                  {error.description}
                </Typography>
              </>
            )}
            {dataConnection && dataConnectionDetails && (
              <>
                {!error && (
                  <Typography variant="body-large" mb="$12">
                    {dataConnection.name}
                  </Typography>
                )}
                <Box display="flex" flexDirection="column" gap="$4">
                  {dataConnectionDetails.map(([key, value]) => (
                    <Typography variant="body-medium" key={key}>
                      <Typography variant="body-medium" color="content.subtle.light" as="span">
                        {snakeCaseToCamelCase(key)}:
                      </Typography>{' '}
                      {value}
                    </Typography>
                  ))}
                </Box>
              </>
            )}
            {action && (
              <Box display="flex" pt="$12" justifyContent="flex-end">
                {action}
              </Box>
            )}
            {dataConnection && !error && canCreateAgents && (
              <Box display="flex" pt="$12" justifyContent="flex-end">
                <Button onClick={() => setIsUpdateConnectionOpen(true)} flex={1} round>
                  Configure Connection
                </Button>
              </Box>
            )}
          </Box>
        )}
      </PopoverContent>
      {dataConnectionId && isUpdateConnectionOpen && (
        <UpdateDataConnection dataConnectionId={dataConnectionId} onClose={onCloseUpdateConnection} />
      )}
    </>
  );
};
