import { ReplayResult, Trace } from '../types';
import { Brain, MessageSquare, Wrench, Clock } from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';
import { JsonYamlFormatter } from './JsonYamlFormatter';

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

export function TraceDisplay({ trace }: { trace: Trace }) {
  return (
    <div className="border-t border-gray-200 p-4 space-y-6">
      <div className="rounded-lg bg-gray-50 p-4">
        <p className="text-sm text-gray-600 mb-1">
          <strong>Agent Name:</strong> {trace.environment.agent_name}
        </p>
        <p className="text-sm text-gray-600 mb-1">
          <strong>Agent Server Version:</strong> {trace.environment.agent_server_version}
        </p>
        <p className="text-sm text-gray-600 mb-1">
          <strong>Platform:</strong> {trace.environment.platform}
        </p>
        <p className="text-sm text-gray-600 mb-1">
          <strong>Name:</strong> {trace.environment.name}
        </p>
      </div>

      {trace.messages && trace.messages.length > 0 && (
        <div className="space-y-4">
          <h3 className="font-medium text-gray-900 flex items-center">
            <MessageSquare className="h-4 w-4 mr-2" />
            Conversation ({trace.messages.length} messages)
          </h3>

          {trace.messages.map((message, messageIndex) => (
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

              <div className="space-y-3">
                {message.content?.map((content, contentIndex) => {
                  if (content.type === 'thought') {
                    return (
                      <div key={contentIndex} className="flex items-start space-x-2">
                        <Brain className="h-4 w-4 text-purple-500 mt-0.5 flex-shrink-0" />
                        <div className="flex-1">
                          <div className="text-xs font-medium text-purple-700 mb-1">Thought</div>
                          <div className="text-sm text-gray-700 italic">{(content as any).thought}</div>
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
                            <MarkdownRenderer content={(content as any).text} />
                          </div>
                        </div>
                      </div>
                    );
                  }

                  if (content.type === 'tool_use') {
                    const toolData = content as any;
                    return (
                      <div key={contentIndex} className="border rounded-md p-3 bg-white">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center space-x-2">
                            <Wrench className="h-4 w-4 text-green-500" />
                            <span className="text-sm font-medium text-green-700">Tool: {toolData.tool_name}</span>
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
                      <strong>Unknown content type:</strong> "{content.type}"
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
