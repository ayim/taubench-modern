import { AgentStatus, AgentMetadata } from '../types';
import { CheckCircle, Clock, AlertCircle, Loader2 } from 'lucide-react';
import { AgentTimer } from './AgentTimer';

interface AgentResultsProps {
  agentName: string;
  agentStatus: AgentStatus;
  metadata?: AgentMetadata;
}

export function AgentResults({ agentName, agentStatus, metadata }: AgentResultsProps) {
  const progress = agentStatus.total_tests > 0 ? (agentStatus.completed_tests / agentStatus.total_tests) * 100 : 0;
  const successRate =
    agentStatus.completed_tests > 0 ? (agentStatus.passed_tests / agentStatus.completed_tests) * 100 : 0;

  const getStatusIcon = () => {
    switch (agentStatus.status) {
      case 'running':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusColor = () => {
    switch (agentStatus.status) {
      case 'running':
        return 'border-blue-200 bg-blue-50';
      case 'completed':
        return 'border-green-200 bg-green-50';
      case 'failed':
        return 'border-red-200 bg-red-50';
      default:
        return 'border-gray-200 bg-gray-50';
    }
  };

  return (
    <div className={`bg-white rounded-lg border-2 p-4 ${getStatusColor()}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium text-gray-900 truncate">{agentName}</h3>
        <div className="flex items-center space-x-2">
          <AgentTimer
            startedAt={agentStatus.started_at}
            completedAt={agentStatus.completed_at}
            isRunning={agentStatus.status === 'running'}
          />
          {getStatusIcon()}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-gray-600 mb-1">
          <span>Progress</span>
          <span>
            {agentStatus.completed_tests} / {agentStatus.total_tests}
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div className="h-2 bg-blue-600 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
        </div>
      </div>

      {/* Current Test */}
      {agentStatus.current_test && (
        <div className="mb-3 p-2 bg-blue-50 border border-blue-200 rounded text-xs">
          <div className="flex items-center space-x-1">
            <Loader2 className="h-3 w-3 animate-spin text-blue-500" />
            <span className="text-blue-700">
              Running: {agentStatus.current_test.test_name} ({agentStatus.current_test.platform})
            </span>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="text-center">
          <div className="text-green-600 font-semibold">{agentStatus.passed_tests}</div>
          <div className="text-gray-500">Passed</div>
        </div>
        <div className="text-center">
          <div className="text-red-600 font-semibold">{agentStatus.failed_tests}</div>
          <div className="text-gray-500">Failed</div>
        </div>
        <div className="text-center">
          <div className="text-gray-900 font-semibold">
            {agentStatus.completed_tests > 0 ? `${successRate.toFixed(0)}%` : '-'}
          </div>
          <div className="text-gray-500">Success</div>
        </div>
      </div>

      {/* Error */}
      {agentStatus.error && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
          Error: {agentStatus.error}
        </div>
      )}

      {/* Metadata info */}
      {metadata && (
        <div className="mt-3 pt-3 border-t border-gray-200 text-xs text-gray-500">
          {metadata.test_cases.length} test case{metadata.test_cases.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}
