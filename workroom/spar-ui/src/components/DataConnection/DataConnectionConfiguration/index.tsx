import { FC } from 'react';
import { useNavigate, useParams } from '../../../hooks';
import { CreateDataConnection } from './components/Create';
import { UpdateDataConnection } from './components/Update';

type Props = {
  snowflakeLinkedUser?: string;
};

export const DataConnectionConfiguration: FC<Props> = ({ snowflakeLinkedUser }) => {
  const navigate = useNavigate();
  const { dataConnectionId } = useParams({ strict: false });

  const onClose = () => {
    navigate({ to: '/data-connections', params: {} });
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
