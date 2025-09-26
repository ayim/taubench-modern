import type { Trial } from '../types';
import { getTrialOverallStatus } from '../utils';

export const getPassFailCounts = (trials: Trial[]): {
  passed: number;
  failed: number;
  canceled: number;
} => {
  let passed = 0;
  let failed = 0;
  let canceled = 0;
  
  trials.forEach(trial => {
    if (trial.status === 'CANCELED') {
      canceled += 1;
    } else if (trial.status === 'ERROR') {
      failed += 1;
    } else if (trial.status === 'COMPLETED') {
      const trialStatus = getTrialOverallStatus(trial);
      if (trialStatus === 'passed') {
        passed += 1;
      } else if (trialStatus === 'failed') {
        failed += 1;
      }
    }
    // Skip pending/executing trials as they don't count towards final results
  });
  
  return { passed, failed, canceled };
};
