import React, { useState } from 'react';
import { Clock3, ListChecks, ListX, LineChartIcon, TestTube2, ChevronDown } from 'lucide-react';
import { TestResultGroup, TrialResult } from '../types';

interface TestResultsListProps {
  results: TestResultGroup[];
}

const getTotalDuration = (trials: TrialResult[]): string => {
  const totalMs = trials.reduce((sum, trial) => {
    if (trial.started_at && trial.completed_at) {
      const start = new Date(trial.started_at).getTime();
      const end = new Date(trial.completed_at).getTime();
      if (!isNaN(start) && !isNaN(end)) {
        return sum + (end - start);
      }
    }
    return sum;
  }, 0);

  const totalSeconds = Math.floor(totalMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds}s`;
};

function binomial(n: number, k: number): number {
  if (k < 0 || k > n) return 0;
  if (k === 0 || k === n) return 1;

  let res = 1;
  for (let i = 1; i <= k; i++) {
    res *= n - (k - i);
    res /= i;
  }
  return res;
}

function passAtK(n: number, c: number, k: number): number {
  if (k > n || n === 0) return 0;
  if (c === 0) return 0;

  const totalComb = binomial(n, k);
  const failComb = binomial(n - c, k);

  return 1 - failComb / totalComb;
}

function passHatK(n: number, c: number, k: number): number {
  if (k > n || n === 0) return 0;
  if (c === 0) return 0;

  return binomial(c, k) / binomial(n, k);
}

const computeMetric = (metric: { name: string; k: number }, trials: TrialResult[]): string => {
  const total = trials.length;
  const successful = trials.filter((trial) => trial.success).length;

  console.log('alternative pass^k', ((successful / total) ** metric.k * 100).toFixed(2));

  if (metric.name === 'pass^k') {
    return `${(passHatK(total, successful, metric.k) * 100).toFixed(2)}%`;
  }
  if (metric.name === 'pass@k') {
    return `${(passAtK(total, successful, metric.k) * 100).toFixed(2)}%`;
  }

  return '??';
};

const getMetricName = (metric: { name: string; k: number }): string => {
  if (metric.name === 'pass^k') {
    return `pass^${metric.k}`;
  }
  if (metric.name === 'pass@k') {
    return `pass@${metric.k}`;
  }

  return metric.name;
};

export const TestResultsSummary: React.FC<TestResultsListProps> = ({ results }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="p-4 border-b border-gray-200 cursor-pointer" onClick={() => setIsOpen((prev) => !prev)}>
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900 mb-0">Test Results Summary</h2>
          <ChevronDown className={`w-5 h-5 text-gray-600 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </div>
      </div>
      {isOpen && (
        <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
          {results.map((group, index) => {
            const total = group.trials.length;
            const passed = group.trials.filter((t) => t.success).length;
            const failed = total - passed;
            const duration = getTotalDuration(group.trials);

            return (
              <div key={index} className="p-4 cursor-pointer hover:bg-gray-50 transition-colors">
                <h2 className="text-xl font-semibold mb-2 flex items-center gap-2">
                  <TestTube2 className="w-5 h-5 text-blue-500" />
                  {group.test_name} <span className="text-sm text-gray-500">({group.platform})</span>
                </h2>

                <div className="text-sm text-gray-700 flex flex-wrap gap-4 mb-3">
                  <div className="flex items-center gap-1">
                    <ListChecks className="w-4 h-4 text-green-600" /> {passed} passed
                  </div>
                  <div className="flex items-center gap-1">
                    <ListX className="w-4 h-4 text-red-600" /> {failed} failed
                  </div>
                  {group.test_case.trials > 1 &&
                    group.test_case.metrics.map((metric) => (
                      <div className="flex items-center gap-1">
                        <LineChartIcon className="w-4 h-4 text-green-600" /> {computeMetric(metric, group.trials)}{' '}
                        {getMetricName(metric)}
                      </div>
                    ))}

                  <div className="flex items-center gap-1">
                    <Clock3 className="w-4 h-4 text-gray-600" /> {duration} total
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="font-medium">{total}</span> trials
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
