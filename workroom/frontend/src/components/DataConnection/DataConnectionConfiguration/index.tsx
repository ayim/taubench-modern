import { FC } from 'react';
import { useNavigate, useParams } from '@tanstack/react-router';
import { CreateDataConnection } from './components/Create';
import { UpdateDataConnection } from './components/Update';

type Props = {
  snowflakeLinkedUser?: string;
};

export const DataConnectionConfiguration: FC<Props> = ({ snowflakeLinkedUser }) => {
  const navigate = useNavigate();
  const { dataConnectionId, tenantId = '' } = useParams({ strict: false });

  const onClose = () => {
    navigate({ to: '/tenants/$tenantId/data-access/data-connections', params: { tenantId } });
  };

  if (dataConnectionId) {
    return (
      <UpdateDataConnection
        snowflakeLinkedUser={snowflakeLinkedUser}
        dataConnectionId={dataConnectionId}
        onClose={onClose}
      />
    );
  }

  return <CreateDataConnection snowflakeLinkedUser={snowflakeLinkedUser} onClose={onClose} />;
};
