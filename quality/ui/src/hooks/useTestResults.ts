import { useState, useEffect, useCallback } from 'react';
import { TestStatus, AgentStatus, OverallStats, TestResult, Agent, DiscoveredAgents } from '../types';

export function useTestResults({ homeFolder }: { homeFolder: string }) {
  const [overallStatus, setOverallStatus] = useState<OverallStats | null>(null);
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>([]);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [discoveredAgents, setDiscoveredAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runStartTime, setRunStartTime] = useState<string | null>(null);
  const [runEndTime, setRunEndTime] = useState<string | null>(null);

  const fetchDiscoveredAgents = useCallback(async () => {
    try {
      const agentsResponse = await fetch('/api/quality_results/agents.json', {
        headers: {
          'x-quality-home-folder': homeFolder,
        },
      });
      if (agentsResponse.ok) {
        const agentsData: DiscoveredAgents = await agentsResponse.json();
        setDiscoveredAgents(agentsData.agents);
      } else {
        // If agents.json doesn't exist yet, that's okay - we'll show agents as they become available
        console.log('agents.json not found, will show agents as they become available');
        setDiscoveredAgents([]);
      }
    } catch (error) {
      console.warn('Could not fetch discovered agents:', error);
      setDiscoveredAgents([]);
    }
  }, [homeFolder]);

  const fetchTestResults = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch status.json
      const statusResponse = await fetch('/api/quality_results/status.json', {
        headers: {
          'x-quality-home-folder': homeFolder,
        },
      });
      if (!statusResponse.ok) {
        throw new Error(`Failed to fetch status: ${statusResponse.statusText}`);
      }

      const statusData: TestStatus = await statusResponse.json();

      // Set overall stats and agent statuses
      setOverallStatus(statusData.overall_stats);

      // Set timing information
      setRunStartTime(statusData.started_at);
      setRunEndTime(statusData.completed_at || null);

      // Merge discovered agents with running agent statuses to show all agents
      const runningAgents = Object.entries(statusData.agents).map(([name, agent]) => ({
        ...agent,
        name,
      }));

      // Update discovered agents with current status from running agents
      setDiscoveredAgents((currentDiscoveredAgents) => {
        const updatedDiscoveredAgents = currentDiscoveredAgents.map((agent) => {
          const runningAgent = runningAgents.find((ra) => ra.name === agent.name);
          return {
            ...agent,
            status: (runningAgent?.status as Agent['status']) || 'pending',
          };
        });

        // Add any running agents that weren't in discovered agents (fallback)
        const missingAgents = runningAgents
          .filter((ra) => !currentDiscoveredAgents.some((da) => da.name === ra.name))
          .map((ra) => ({
            name: ra.name,
            zip_path: '',
            path: '',
            status: ra.status as Agent['status'],
          }));

        return [...updatedDiscoveredAgents, ...missingAgents];
      });

      setAgentStatuses(runningAgents);

      // Try to fetch the run data directory listing to get all test result files
      const runDir = statusData.current_run_dir?.split('/').pop() || statusData.run_id;

      try {
        // Get list of test result files from the current run
        const filesResponse = await fetch(`/api/quality_results/runs/${runDir}/`, {
          headers: {
            'x-quality-home-folder': homeFolder,
          },
        });
        if (filesResponse.ok) {
          const filesText = await filesResponse.text();

          // Parse the directory listing or file names
          // For now, we'll build test results from completed test files
          // Real file names look like: 001-quality-basic-browsing_one-step-browse_azure_0.json
          const filePattern = /([-\w]+)_([-\w]+)_([-\w]+)_([-\w]+)\.json/g;
          const matches = [...filesText.matchAll(filePattern)];

          const results: TestResult[] = [];

          for (const match of matches) {
            const filename = match[0];
            const agentName = match[1];
            const testNameFromFile = match[2];
            const platformFromFile = match[3];
            const trialIdFromFile = match[4];

            try {
              // Fetch the individual test result file
              const testResponse = await fetch(`/api/quality_results/runs/${runDir}/${filename}`, {
                headers: {
                  'x-quality-home-folder': homeFolder,
                },
              });
              if (testResponse.ok) {
                const testData = await testResponse.json();

                const normalizedResult: TestResult = {
                  ...testData,
                  agent_name: testData.agent_name ?? agentName,
                  test_name: testData.test_name ?? testNameFromFile,
                  platform: testData.platform ?? platformFromFile,
                  trial_id: String(testData.trial_id ?? trialIdFromFile ?? filename.replace('.json', '')),
                  agent_id: testData.agent_id ?? null,
                  thread_id: testData.thread_id ?? null,
                };

                results.push(normalizedResult);
              }
            } catch (error) {
              console.warn(`Failed to fetch test result ${filename}:`, error);
            }
          }

          setTestResults(results);
        }
      } catch (filesError) {
        console.warn('Could not fetch test result files:', filesError);
        // Fallback: create mock results from agent status
        setTestResults([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch test results');
    } finally {
      setLoading(false);
    }
  }, [homeFolder]);

  const fetchIndividualTestResult = useCallback(
    async (
      agentName: string,
      testName: string,
      platform: string,
      trialId: string,
      runId: string,
    ): Promise<TestResult | null> => {
      try {
        // Real file naming pattern: {agentName}_{testName}_{platform}_{trialId}.json
        const filename = `${agentName}_${testName}_${platform}_${trialId}.json`;
        const response = await fetch(`/api/quality_results/runs/${runId}/${filename}`, {
          headers: {
            'x-quality-home-folder': homeFolder,
          },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch test result: ${response.statusText}`);
        }

        const testData = await response.json();
        return {
          ...testData,
          agent_name: testData.agent_name ?? agentName,
          test_name: testData.test_name ?? testName,
          platform: testData.platform ?? platform,
          trial_id: String(testData.trial_id ?? trialId),
          agent_id: testData.agent_id ?? null,
          thread_id: testData.thread_id ?? null,
        };
      } catch (error) {
        console.error('Failed to fetch individual test result:', error);
        return null;
      }
    },
    [homeFolder],
  );

  // Filter test results based on selected agent
  const filteredTestResults = selectedAgent
    ? testResults.filter((result) => result.agent_name === selectedAgent)
    : testResults;

  useEffect(() => {
    fetchDiscoveredAgents();
  }, [fetchDiscoveredAgents]);

  useEffect(() => {
    fetchTestResults();
    // Poll every 2 seconds for updates
    const interval = setInterval(fetchTestResults, 2000);
    return () => clearInterval(interval);
  }, [fetchTestResults]);

  return {
    overallStatus,
    agentStatuses,
    testResults: filteredTestResults,
    discoveredAgents,
    selectedAgent,
    setSelectedAgent,
    loading,
    error,
    refetch: fetchTestResults,
    fetchIndividualTestResult,
    runStartTime,
    runEndTime,
  };
}
