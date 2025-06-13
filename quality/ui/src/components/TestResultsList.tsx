import { TestResult } from '../types';
import {
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronRight,
  Brain,
  MessageSquare,
  Wrench,
  Clock,
  Loader2,
  Star,
} from 'lucide-react';
import { useState } from 'react';
import { TestTimer } from './TestTimer';
import { MarkdownRenderer } from './MarkdownRenderer';
import { JsonYamlFormatter } from './JsonYamlFormatter';

interface TestResultsListProps {
  results: TestResult[];
  onFetchTestResult?: (
    agentName: string,
    testName: string,
    platform: string,
    runId: string,
  ) => Promise<TestResult | null>;
  currentRunId?: string;
}

export function TestResultsList({ results, onFetchTestResult, currentRunId }: TestResultsListProps) {
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set());
  const [loadingDetails, setLoadingDetails] = useState<Set<string>>(new Set());
  const [fullTestResults, setFullTestResults] = useState<Map<string, TestResult>>(new Map());

  const toggleExpanded = async (result: TestResult) => {
    const resultId = `${result.agent_name || 'unknown'}_${result.test_name}_${result.platform}`;
    const newExpanded = new Set(expandedResults);

    if (newExpanded.has(resultId)) {
      newExpanded.delete(resultId);
    } else {
      newExpanded.add(resultId);

      // If we don't have full details and we have a fetch function, load them
      if (!fullTestResults.has(resultId) && onFetchTestResult && currentRunId) {
        setLoadingDetails((prev) => new Set(prev).add(resultId));

        // Extract agent name from test result
        const agentName = result.agent_name || result.test_case?.file_path?.split('/')[2] || 'unknown-agent';

        try {
          const fullResult = await onFetchTestResult(agentName, result.test_name, result.platform, currentRunId);
          if (fullResult) {
            setFullTestResults((prev) => new Map(prev).set(resultId, fullResult));
          }
        } catch (error) {
          console.error('Failed to fetch test details:', error);
        } finally {
          setLoadingDetails((prev) => {
            const newSet = new Set(prev);
            newSet.delete(resultId);
            return newSet;
          });
        }
      }
    }
    setExpandedResults(newExpanded);
  };

  const calculateAverageLLMScore = (evaluations: any[]) => {
    const llmEvals = evaluations.filter((evaluation) => evaluation.kind === 'llm-eval-of-last-agent-turn');
    if (llmEvals.length === 0) return null;

    let totalScore = 0;
    let validScores = 0;

    llmEvals.forEach((evaluation) => {
      try {
        const parsed = JSON.parse(evaluation.actual_value);
        if (typeof parsed.score === 'number') {
          totalScore += parsed.score / 10.0;
          validScores++;
        }
      } catch {
        // Ignore invalid JSON
      }
    });

    return validScores > 0 ? totalScore / validScores : null;
  };

  const formatTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString();
    } catch {
      return timestamp;
    }
  };

  const formatDuration = (startTime: string, endTime: string) => {
    try {
      const start = new Date(startTime).getTime();
      const end = new Date(endTime).getTime();
      const duration = (end - start) / 1000;
      return `${duration.toFixed(2)}s`;
    } catch {
      return 'N/A';
    }
  };

  if (results.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
        <p className="text-gray-500">No test results available yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {results.map((result) => {
        const resultId = `${result.agent_name || 'unknown'}_${result.test_name}_${result.platform}`;
        const isExpanded = expandedResults.has(resultId);
        const isLoading = loadingDetails.has(resultId);
        const fullResult = fullTestResults.get(resultId) || result;

        // Calculate average LLM score for this test
        const avgLLMScore = fullResult.evaluation_results
          ? calculateAverageLLMScore(fullResult.evaluation_results)
          : null;

        return (
          <div key={resultId} className="bg-white rounded-lg border border-gray-200">
            {/* Summary Row */}
            <div className="flex items-center justify-between p-4">
              <div
                className="flex items-center space-x-3 cursor-pointer hover:bg-gray-50 flex-1 rounded"
                onClick={() => toggleExpanded(result)}
              >
                {result.success ? (
                  <CheckCircle className="h-5 w-5 text-green-500" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-500" />
                )}
                <div>
                  <h4 className="font-medium text-gray-900">
                    {result.agent_name ? `${result.agent_name}/${result.test_name}` : result.test_name}
                  </h4>
                  <p className="text-sm text-gray-600">
                    {result.platform} ({fullResult.agent_messages.length} messages)
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <div className="text-right">
                  <div className="flex items-center space-x-2">
                    {avgLLMScore !== null && (
                      <div className="flex items-center space-x-1">
                        <Star className="h-3 w-3 text-amber-500" />
                        <span
                          className={`text-xs font-medium px-2 py-1 rounded-full w-20 ${
                            avgLLMScore >= 0.8
                              ? 'bg-green-100 text-green-700'
                              : avgLLMScore >= 0.6
                                ? 'bg-yellow-100 text-yellow-700'
                                : 'bg-red-100 text-red-700'
                          }`}
                        >
                          {(avgLLMScore * 10).toFixed(1)} / 10.0
                        </span>
                      </div>
                    )}
                    {/* <span className={`text-sm font-medium ${result.success ? 'text-green-600' : 'text-red-600'}`}>
                      {result.success ? 'PASSED' : 'FAILED'}
                    </span> */}
                  </div>
                  <div className="flex items-center space-x-2 text-xs text-gray-500">
                    <span>{formatTime(result.completed_at)}</span>
                    <TestTimer startedAt={result.started_at} completedAt={result.completed_at} showIcon={false} />
                  </div>
                </div>

                <button
                  onClick={() => toggleExpanded(result)}
                  className="p-1 hover:bg-gray-100 rounded flex items-center space-x-1"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 text-gray-400 animate-spin" />
                  ) : isExpanded ? (
                    <ChevronDown className="h-4 w-4 text-gray-400" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-gray-400" />
                  )}
                </button>
              </div>
            </div>

            {/* Expanded Details */}
            {isExpanded && (
              <div className="border-t border-gray-200 p-4 space-y-6">
                {/* Test Case Info */}
                <div className="rounded-lg bg-gray-50 p-4">
                  <h3 className="font-medium text-gray-900 mb-2">Test Case</h3>
                  <p className="text-sm text-gray-600 mb-1">
                    <strong>Description:</strong> {fullResult.test_case?.description || 'No description'}
                  </p>
                  <p className="text-sm text-gray-600 mb-1">
                    <strong>File:</strong> {fullResult.test_case?.file_path || 'Unknown'}
                  </p>
                  {fullResult.started_at && (
                    <div className="flex items-center justify-between text-sm text-gray-600">
                      <div>
                        <strong>Duration:</strong>
                        <TestTimer
                          startedAt={fullResult.started_at}
                          completedAt={fullResult.completed_at}
                          className="ml-2"
                        />
                      </div>
                      <div className="text-xs text-gray-500">
                        Started: {formatTime(fullResult.started_at)} | Completed: {formatTime(fullResult.completed_at)}
                      </div>
                    </div>
                  )}
                </div>

                {/* Error Message */}
                {fullResult.error && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded">
                    <h5 className="text-sm font-medium text-red-800 mb-1">Error</h5>
                    <p className="text-sm text-red-700">{fullResult.error}</p>
                  </div>
                )}

                {/* Conversation Messages */}
                {fullResult.agent_messages && fullResult.agent_messages.length > 0 && (
                  <div className="space-y-4">
                    <h3 className="font-medium text-gray-900 flex items-center">
                      <MessageSquare className="h-4 w-4 mr-2" />
                      Conversation ({fullResult.agent_messages.length} messages)
                    </h3>

                    {fullResult.agent_messages.map((message, messageIndex) => (
                      <div
                        key={messageIndex}
                        className={`rounded-lg border p-4 ${
                          message.role === 'agent' ? 'border-blue-200 bg-blue-50' : 'border-gray-200 bg-gray-50'
                        }`}
                      >
                        <div className="flex items-center mb-3">
                          <span
                            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                              message.role === 'agent' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                            }`}
                          >
                            {message.role === 'agent' ? '🤖 Agent' : '👤 User'}
                          </span>
                        </div>

                        {/* Message Content */}
                        <div className="space-y-3">
                          {message.content?.map((content, contentIndex) => {
                            if (content.type === 'thought') {
                              return (
                                <div key={contentIndex} className="flex items-start space-x-2">
                                  <Brain className="h-4 w-4 text-purple-500 mt-0.5 flex-shrink-0" />
                                  <div className="flex-1">
                                    <div className="text-xs font-medium text-purple-700 mb-1">Thought</div>
                                    <div className="text-sm text-gray-700 italic">{(content.data as any).thought}</div>
                                  </div>
                                </div>
                              );
                            }

                            if (content.type === 'text') {
                              return (
                                <div key={contentIndex} className="flex items-start space-x-2">
                                  <MessageSquare className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                                  <div className="flex-1">
                                    <div className="text-xs font-medium text-blue-700 mb-1">Text</div>
                                    <div className="text-sm text-gray-900">
                                      <MarkdownRenderer content={(content.data as any).text} />
                                    </div>
                                  </div>
                                </div>
                              );
                            }

                            if (content.type === 'tool_use') {
                              const toolData = content.data as any;
                              return (
                                <div key={contentIndex} className="border rounded-md p-3 bg-white">
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center space-x-2">
                                      <Wrench className="h-4 w-4 text-green-500" />
                                      <span className="text-sm font-medium text-green-700">
                                        Tool: {toolData.tool_name}
                                      </span>
                                    </div>
                                    <div className="flex items-center space-x-2 text-xs text-gray-500">
                                      <Clock className="h-3 w-3" />
                                      {toolData.started_at && toolData.ended_at && (
                                        <span>{formatDuration(toolData.started_at, toolData.ended_at)}</span>
                                      )}
                                    </div>
                                  </div>

                                  <div className="space-y-3">
                                    <JsonYamlFormatter
                                      content={toolData.input_as_string}
                                      label="Input"
                                      maxHeight="max-h-24"
                                      defaultExpanded={false}
                                    />

                                    <JsonYamlFormatter
                                      content={
                                        typeof toolData.output_as_string === 'string'
                                          ? toolData.output_as_string
                                          : JSON.stringify(toolData.output_as_string, null, 2)
                                      }
                                      label="Output"
                                      maxHeight="max-h-32"
                                      defaultExpanded={false}
                                    />

                                    {toolData.error && (
                                      <div>
                                        <div className="text-xs font-medium text-red-600 mb-1">Error:</div>
                                        <div className="text-xs bg-red-50 border border-red-200 rounded p-2 text-red-700 font-mono max-h-24 overflow-y-auto">
                                          {toolData.error}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              );
                            }

                            return (
                              <div key={contentIndex} className="text-sm text-gray-600">
                                <strong>Unknown content type:</strong> {content.type}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Evaluation Results */}
                {fullResult.evaluation_results && fullResult.evaluation_results.length > 0 && (
                  <div>
                    <h3 className="font-medium text-gray-900 mb-3">Evaluation Results</h3>
                    <div className="space-y-3">
                      {fullResult.evaluation_results.map((evaluation, index) => {
                        const isLLMEval = evaluation.kind === 'llm-eval-of-last-agent-turn';

                        // Parse LLM evaluation data
                        let llmData = null;
                        if (isLLMEval) {
                          try {
                            llmData = JSON.parse(evaluation.actual_value);
                          } catch {
                            // If parsing fails, fall back to showing raw value
                          }
                        }

                        return (
                          <div
                            key={index}
                            className={`border rounded-md p-4 ${
                              isLLMEval ? 'border-purple-200 bg-purple-50' : 'border-gray-200'
                            }`}
                          >
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center space-x-2">
                                {evaluation.passed ? (
                                  <CheckCircle className="h-5 w-5 text-green-500" />
                                ) : (
                                  <XCircle className="h-5 w-5 text-red-500" />
                                )}
                                <span className={`font-medium ${isLLMEval ? 'text-purple-800' : 'text-gray-900'}`}>
                                  {isLLMEval ? '🧠 LLM Evaluation' : evaluation.kind}
                                </span>
                                {isLLMEval && (
                                  <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded-full">
                                    AI Assessment
                                  </span>
                                )}
                              </div>

                              <div className="flex items-center space-x-2">
                                {/* Show individual LLM score prominently */}
                                {isLLMEval && llmData?.score !== undefined && (
                                  <div className="flex items-center space-x-1">
                                    <Star className="h-4 w-4 text-amber-500" />
                                    <span
                                      className={`text-sm font-bold px-2 py-1 rounded-full ${
                                        llmData.score >= 0.8
                                          ? 'bg-green-100 text-green-800'
                                          : llmData.score >= 0.6
                                            ? 'bg-yellow-100 text-yellow-800'
                                            : 'bg-red-100 text-red-800'
                                      }`}
                                    >
                                      {llmData.score.toFixed(1)} / 10.0
                                    </span>
                                  </div>
                                )}
                                <span
                                  className={`text-xs px-3 py-1 rounded-full font-medium ${
                                    evaluation.passed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                                  }`}
                                >
                                  {evaluation.passed ? 'PASSED' : 'FAILED'}
                                </span>
                              </div>
                            </div>

                            <div className="space-y-3">
                              {/* Expected criteria */}
                              <div className={`text-sm ${isLLMEval ? 'text-purple-700' : 'text-gray-700'}`}>
                                <strong>Expected:</strong> {evaluation.expected}
                              </div>

                              {/* LLM Evaluation specific details */}
                              {isLLMEval && llmData && (
                                <div className="bg-white rounded-md p-3 border border-purple-200">
                                  <span className="text-sm font-medium text-purple-800">Assessment: </span>
                                  <p className="text-sm text-gray-700 mt-1 leading-relaxed">
                                    {llmData.explanation || llmData.reasoning || 'No explanation provided'}
                                  </p>
                                </div>
                              )}

                              {/* Fallback for LLM eval without proper JSON */}
                              {isLLMEval && !llmData && (
                                <div className="bg-white rounded-md p-3 border border-purple-200">
                                  <span className="text-sm font-medium text-purple-800">Assessment: </span>
                                  <p className="text-sm text-gray-700 mt-1 leading-relaxed">
                                    {evaluation.actual_value}
                                  </p>
                                </div>
                              )}

                              {/* Non-LLM evaluation actual value */}
                              {!isLLMEval && !evaluation.passed && (
                                <div className="text-sm text-gray-600">
                                  <strong>Actual:</strong> {evaluation.actual_value}
                                </div>
                              )}

                              {/* Error handling */}
                              {evaluation.error && (
                                <div className="text-red-600 bg-red-50 p-2 rounded border border-red-200">
                                  <strong className="text-sm">Error:</strong>
                                  <p className="text-sm mt-1">{evaluation.error}</p>
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
