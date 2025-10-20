import { OverallStats } from '../types';
import { CheckCircle, XCircle, Clock, Users } from 'lucide-react';

interface OverallStatsCardProps {
  stats: OverallStats;
  isRunning: boolean;
}

export function OverallStatsCard({ stats, isRunning }: OverallStatsCardProps) {
  const completionRate = stats.total_tests > 0 ? (stats.completed_tests / stats.total_tests) * 100 : 0;
  const successRate = stats.completed_tests > 0 ? (stats.passed_tests / stats.completed_tests) * 100 : 0;

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-lg font-medium text-gray-900 mb-3">Overall Progress</h3>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-gray-600 mb-1">
          <span>Tests Completed</span>
          <span>
            {stats.completed_tests} / {stats.total_tests}
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-300 ${isRunning ? 'bg-blue-600' : 'bg-green-600'}`}
            style={{ width: `${completionRate}%` }}
          />
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="flex items-center space-x-2">
          <Users className="h-4 w-4 text-gray-400" />
          <div>
            <p className="text-xs text-gray-600">Agents</p>
            <p className="text-base font-semibold">
              {stats.completed_agents} / {stats.total_agents}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <Clock className="h-4 w-4 text-blue-500" />
          <div>
            <p className="text-xs text-gray-600">Total Tests</p>
            <p className="text-base font-semibold">{stats.total_tests}</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <CheckCircle className="h-4 w-4 text-green-500" />
          <div>
            <p className="text-xs text-gray-600">Passed</p>
            <p className="text-base font-semibold text-green-600">{stats.passed_tests}</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <XCircle className="h-4 w-4 text-red-500" />
          <div>
            <p className="text-xs text-gray-600">Failed</p>
            <p className="text-base font-semibold text-red-600">{stats.failed_tests}</p>
          </div>
        </div>
      </div>

      {/* Success Rate */}
      {stats.completed_tests > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <div className="flex justify-between items-center">
            <span className="text-xs text-gray-600">Success Rate</span>
            <span
              className={`text-sm font-medium ${
                successRate >= 80 ? 'text-green-600' : successRate >= 60 ? 'text-yellow-600' : 'text-red-600'
              }`}
            >
              {successRate.toFixed(1)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
