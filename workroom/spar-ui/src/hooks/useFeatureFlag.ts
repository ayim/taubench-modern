import { useSparUIContext } from '../api/context';
import { SparUIFeatureFlag } from '../api';

export const useFeatureFlag = (
  feature: SparUIFeatureFlag,
): { enabled: true } | { enabled: false; message?: string } => {
  const { sparAPIClient } = useSparUIContext();
  return sparAPIClient.useFeatureFlag(feature);
};
