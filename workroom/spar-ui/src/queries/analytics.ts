import { AnalyticsEvent } from '../api';
import { createSparMutation } from './shared';

type TrackVars = { metrics: AnalyticsEvent; value?: string };

const useTrackMutationBase = createSparMutation<Record<string, never>, TrackVars>()(({ sparAPIClient }) => ({
  mutationFn: async ({ metrics, value }) => {
    if (!sparAPIClient.track) {
      // no ops: skip tracking if not defined for the client
      return;
    }

    sparAPIClient
      .track(metrics, value)
      .then(() => {
        // analytics sent, no ops
      })
      .catch((e) => {
        // eslint-disable-next-line no-console
        console.error('Cannot track analytics', e);
      });
  },
}));

// Public hook: exposes track(metrics, value?)
export const useAnalytics = () => {
  const mutation = useTrackMutationBase({});

  const track = (metrics: AnalyticsEvent, value?: string) => mutation.mutate({ metrics, value });

  return { track };
};
