import { useSparUIContext } from '../api/context';

export const useNavigate = () => {
  const { sparAPIClient } = useSparUIContext();
  return sparAPIClient.navigate;
};
