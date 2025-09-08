import { useSparUIContext } from '../api/context';
import { SparUIFeatureFlag } from '../api';

export const useFeatureFlag = (feature: SparUIFeatureFlag): boolean => {
  const { sparAPIClient } = useSparUIContext();
  return sparAPIClient.getFeatureFlag(feature);
};
