import { useNavigate, useParams } from '../../../hooks';
import { CreateDataConnection } from './components/Create';
import { UpdateDataConnection } from './components/Update';

export const DataConnectionConfiguration = () => {
  const navigate = useNavigate();
  const { dataConnectionId } = useParams({ strict: false });

  const onClose = () => {
    navigate({ to: '/data-connections', params: {} });
  };

  if (dataConnectionId) {
    return <UpdateDataConnection dataConnectionId={dataConnectionId} onClose={onClose} />;
  }

  return <CreateDataConnection onClose={onClose} />;
};
