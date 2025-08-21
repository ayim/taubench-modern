import { useTestResults } from './hooks/useTestResults';
import { AgentResults } from './components/AgentResults';
import { AgentsList } from './components/AgentsList';
import { TestResultsSummary } from './components/TestResultsSummary';
import { OverallStatsCard } from './components/OverallStatsCard';
import { RefreshButton } from './components/RefreshButton';
import { RunTimer } from './components/RunTimer';
import { AlertCircle, CheckCircle, Clock, XCircle } from 'lucide-react';
import { TestResultsList } from './components/TestResultsList';
import { TestResult, TestResultGroup } from './types';
import { SettingsButton } from './components/SettingsButton';
import { useState } from 'react';

function groupThreadResults(results: TestResult[]): TestResultGroup[] {
  const groupMap = new Map<string, TestResultGroup>();

  for (const result of results) {
    const key = `${result.test_name}::${result.platform}`;
    if (!groupMap.has(key)) {
      groupMap.set(key, {
        test_name: result.test_name,
        platform: result.platform,
        test_case: result.test_case,
        trials: [],
      });
    }
    groupMap.get(key)!.trials.push({
      trial_id: 'FIXME',
      ...result,
    });
  }

  return Array.from(groupMap.values());
}

function Dashboard() {
  const [settings, setSettings] = useState({
    homeFolder: '~/.sema4x/quality',
  });
  const {
    overallStatus,
    agentStatuses,
    testResults: threadResults,
    discoveredAgents,
    selectedAgent,
    setSelectedAgent,
    loading,
    error,
    refetch,
    runStartTime,
    runEndTime,
  } = useTestResults(settings);

  if (loading && !overallStatus) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading test results...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Error Loading Results</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={refetch}
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // Determine overall run status based on agent statuses
  const getOverallRunStatus = () => {
    if (!overallStatus || agentStatuses.length === 0) return 'unknown';

    const hasRunning = agentStatuses.some((agent) => agent.status === 'running');
    const hasFailed = agentStatuses.some((agent) => agent.status === 'failed');
    const allCompleted = agentStatuses.every((agent) => agent.status === 'completed');

    if (hasRunning) return 'running';
    if (hasFailed) return 'failed';
    if (allCompleted) {
      const hasFailures = agentStatuses.some((agent) => agent.failed_tests > 0);
      return hasFailures ? 'completed-with-failures' : 'completed-success';
    }

    return 'unknown';
  };

  const runStatus = getOverallRunStatus();

  const getStatusIcon = () => {
    switch (runStatus) {
      case 'running':
        return <Clock className="h-6 w-6 text-blue-500" />;
      case 'completed-success':
        return <CheckCircle className="h-6 w-6 text-green-500" />;
      case 'completed-with-failures':
      case 'failed':
        return <XCircle className="h-6 w-6 text-red-500" />;
      default:
        return <Clock className="h-6 w-6 text-gray-500" />;
    }
  };

  const getStatusText = () => {
    switch (runStatus) {
      case 'running':
        return 'Tests Running';
      case 'completed-success':
        return 'All Tests Passed';
      case 'completed-with-failures':
        return 'Tests Completed (Some Failed)';
      case 'failed':
        return 'Tests Failed';
      default:
        return 'Status Unknown';
    }
  };

  const getStatusColor = () => {
    switch (runStatus) {
      case 'running':
        return 'text-blue-600';
      case 'completed-success':
        return 'text-green-600';
      case 'completed-with-failures':
      case 'failed':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const resultsByTest = groupThreadResults(threadResults);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {getStatusIcon()}
              <div>
                <h1 className="text-3xl font-bold text-gray-900">Quality Testing Dashboard</h1>
                <p className={`text-lg ${getStatusColor()}`}>{getStatusText()}</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <RunTimer
                startedAt={runStartTime}
                completedAt={runEndTime}
                className="bg-gray-100 px-3 py-2 rounded-lg"
              />
              <RefreshButton onRefresh={refetch} isLoading={loading} />
              <SettingsButton isLoading={loading} settings={settings} saveSettings={setSettings} />
            </div>
          </div>
        </div>

        {overallStatus ? (
          <div className="space-y-8">
            {/* Overall Stats */}
            <OverallStatsCard stats={overallStatus} isRunning={runStatus === 'running'} />

            {/* Agents List - Show all discovered agents */}
            {discoveredAgents && discoveredAgents.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">Agents ({discoveredAgents.length})</h2>
                <AgentsList agents={discoveredAgents} selectedAgent={selectedAgent} onAgentSelect={setSelectedAgent} />
              </div>
            )}

            {/* Agent Progress - Show only running agents */}
            {agentStatuses.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">
                  Agent Progress ({agentStatuses.length} running)
                </h2>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {agentStatuses.map((agent) => (
                    <AgentResults key={agent.name} agentName={agent.name} agentStatus={agent} />
                  ))}
                </div>
              </div>
            )}

            {resultsByTest.length > 0 && <TestResultsSummary results={resultsByTest} />}

            {threadResults.length > 0 && (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">
                  Thread Results ({threadResults.length})
                  {selectedAgent && (
                    <span className="text-sm font-normal text-gray-600 ml-2">- Filtered by {selectedAgent}</span>
                  )}
                </h2>
                <TestResultsList results={threadResults} />
              </div>
            )}
          </div>
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
            <p className="text-gray-500">No test data available yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
