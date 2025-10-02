import type { Trial } from '../types';

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
      const hasEvaluationResults = trial.evaluation_results && trial.evaluation_results.length > 0;
      if (hasEvaluationResults && trial.evaluation_results?.every(result => result.passed)) {
        passed += 1;
      } else {
        failed += 1;
      }
    }
    // Skip PENDING/EXECUTING trials as they don't count towards final results
  });
  
  return { passed, failed, canceled };
};
