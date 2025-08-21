import { useCallback } from 'react';
import { ReplayResult } from '../types';

export function useReplayResults({ homeFolder }: { homeFolder: string }) {
  const fetchReplayRun = useCallback(
    async (runId: string): Promise<ReplayResult | null> => {
      try {
        const testResponse = await fetch(`/api/replay_results/runs/${runId}/replay_result.json`, {
          headers: {
            'x-quality-home-folder': homeFolder,
          },
        });
        if (testResponse.ok) {
          const testData = await testResponse.json();

          return testData;
        }

        return null;
      } catch (error) {
        console.warn(`Failed to fetch test result ${runId}/replay_result.json:`, error);
        return null;
      }
    },
    [homeFolder],
  );

  return {
    fetchReplayRun,
  };
}
