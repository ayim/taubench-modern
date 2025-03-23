import React, { useState, useRef, useEffect } from "react";

export interface Message {
  role: "user" | "agent";
  content: any[]; // For agent messages with structured content
  message_id?: string; // For user messages
}

// Helper function to render artifact links
const ArtifactLinks: React.FC<{ artifacts: any[] }> = ({ artifacts }) => (
  <div className="mt-2">
    <div className="flex gap-2 flex-wrap">
      {artifacts.map((artifact, idx) => (
        <a
          key={idx}
          href={`cursor://file/${artifact.path}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-shrink-0 text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-full 
                   hover:bg-blue-50 hover:border-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
        >
          {artifact.name || `Artifact ${idx + 1}`}
        </a>
      ))}
    </div>
  </div>
);

// User message component
const UserMessage: React.FC<{ content?: any[], messageId?: string, artifacts: any[] }> = ({ content, messageId, artifacts }) => {
  const messageArtifacts = artifacts.filter(a => a.message_id === messageId);
  
  return (
    <div className="flex flex-col items-end">
      <div 
        className="px-4 py-2 rounded-lg max-w-[70%] bg-blue-600 text-white"
        style={{ whiteSpace: "pre-wrap" }}
      >
        {content?.[0]?.text}
      </div>
      {messageArtifacts.length > 0 && (
        <ArtifactLinks artifacts={messageArtifacts} />
      )}
    </div>
  );
};

// Agent message component
const AgentMessage: React.FC<{ content?: any[], messageId?: string, artifacts: any[] }> = ({ content, messageId, artifacts }) => {
  // State to track which tool call sections are expanded
  const [expandedSections, setExpandedSections] = useState<{[key: string]: boolean}>({});
  
  const messageArtifacts = artifacts.filter(a => a.message_id === messageId);
  
  // Toggle section visibility
  const toggleSection = (toolId: string, section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [`${toolId}-${section}`]: !prev[`${toolId}-${section}`]
    }));
  };
  
  // Check if a section is expanded
  const isSectionExpanded = (toolId: string, section: string) => {
    return !!expandedSections[`${toolId}-${section}`];
  };

  return (
    <div className="flex flex-col">
      <div className="flex justify-start">
        <div 
          className="px-4 py-2 rounded-lg max-w-[70%] bg-gray-100 text-gray-800 border border-gray-200"
          style={{ whiteSpace: "pre-wrap" }}
        >
          <div className="agent-structured-content flex flex-col gap-2">
            {content?.map((item, index) => {
              if (item.kind === "thought") {
                return (
                  <div key={index} className="thought-content italic text-gray-600 border-l-2 border-gray-400 pl-2">
                    {item.thought}
                  </div>
                );
              } else if (item.kind === "text") {
                return (
                  <div key={index} className="text-content">
                    {item.text}
                  </div>
                );
              } else if (item.kind === "tool_call") {
                // Enhanced tool call rendering
                const statusColors = {
                  pending: "bg-gray-100 text-gray-600",
                  running: "bg-blue-100 text-blue-700",
                  streaming: "bg-purple-100 text-purple-700",
                  finished: "bg-green-100 text-green-700",
                  failed: "bg-red-100 text-red-700"
                };

                const statusColor = statusColors[item.status as keyof typeof statusColors] || "bg-gray-100";

                const isLoading = item.status === "running" || item.status === "streaming";
                
                // Try to parse and prettify the arguments
                let prettyArgs = item.arguments_raw;
                try {
                  const parsed = JSON.parse(item.arguments_raw);
                  prettyArgs = JSON.stringify(parsed, null, 2);
                } catch (e) {
                  // Keep original if not valid JSON
                }
                
                // Generate unique ID for this tool call
                const toolId = `tool-${index}`;
                
                return (
                  <div key={index} className="tool-call-content border rounded-md overflow-hidden">
                    <div className="tool-header bg-gray-200 px-3 py-1.5 font-medium flex justify-between items-center">
                      <span>�� {item.name}</span>
                      <div className="flex items-center">
                        {isLoading && (
                          <div className="animate-spin mr-2 h-4 w-4 text-blue-600">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                          </div>
                        )}
                        <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor}`}>
                          {item.status}
                        </span>
                      </div>
                    </div>
                    
                    <div className="px-3 py-2">
                      <div className="tool-args mb-2">
                        <button 
                          onClick={() => toggleSection(toolId, 'args')}
                          className="text-xs text-gray-500 mb-1 flex items-center w-full justify-between hover:bg-gray-50 p-1 rounded"
                        >
                          <span>Arguments:</span>
                          <span className="text-gray-400">{isSectionExpanded(toolId, 'args') ? '▼' : '►'}</span>
                        </button>
                        {isSectionExpanded(toolId, 'args') && (
                          <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">{prettyArgs}</pre>
                        )}
                      </div>
                      
                      {item.result && (
                        <div className="tool-result">
                          <button 
                            onClick={() => toggleSection(toolId, 'result')}
                            className="text-xs text-gray-500 mb-1 flex items-center w-full justify-between hover:bg-gray-50 p-1 rounded"
                          >
                            <span>Result:</span>
                            <span className="text-gray-400">{isSectionExpanded(toolId, 'result') ? '▼' : '►'}</span>
                          </button>
                          {isSectionExpanded(toolId, 'result') && (
                            <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">{item.result}</pre>
                          )}
                        </div>
                      )}
                      
                      {item.error && (
                        <div className="tool-error">
                          <button 
                            onClick={() => toggleSection(toolId, 'error')}
                            className="text-xs text-gray-500 mb-1 flex items-center w-full justify-between hover:bg-gray-50 p-1 rounded"
                          >
                            <span>Error:</span>
                            <span className="text-gray-400">{isSectionExpanded(toolId, 'error') ? '▼' : '►'}</span>
                          </button>
                          {isSectionExpanded(toolId, 'error') && (
                            <pre className="text-xs bg-red-50 text-red-700 p-2 rounded overflow-x-auto">{item.error}</pre>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              }
              return null;
            })}
          </div>
        </div>
      </div>
      {messageArtifacts.length > 0 && (
        <div className="flex justify-start mt-1 ml-2">
          <ArtifactLinks artifacts={messageArtifacts} />
        </div>
      )}
    </div>
  );
};

interface ChatPanelProps {
  threadName: string;
  messages: Message[];
  onSendMessage: (text: string) => void;
  isLoading: boolean;
  activeThreadArtifacts: any[]; // Now expects artifacts with message_id property
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  threadName,
  messages,
  onSendMessage,
  isLoading,
  activeThreadArtifacts,
}) => {
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const handleSend = () => {
    const text = inputValue.trim();
    if (!text) return;
    onSendMessage(text);
    setInputValue("");
  };
  
  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Filter for artifacts not associated with any message
  const unassociatedArtifacts = activeThreadArtifacts.filter(artifact => !artifact.message_id);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 px-4 py-2">
        <h2 className="font-semibold text-gray-800">
          {threadName || "No thread selected"}
        </h2>
      </div>
      
      {/* Messages area - scrollable */}
      <div className="flex-1 overflow-y-auto bg-gray-50 p-4">
        <div className="flex flex-col space-y-3">
          {messages.map((msg, idx) => (
            <div key={idx}>
              {msg.role === "user" ? (
                <UserMessage 
                  content={msg.content}
                  messageId={msg.message_id} 
                  artifacts={activeThreadArtifacts}
                />
              ) : (
                <AgentMessage 
                  content={msg.content}
                  messageId={msg.message_id} 
                  artifacts={activeThreadArtifacts}
                />
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>
      
      {/* Artifacts section - only for unassociated artifacts */}
      {unassociatedArtifacts.length > 0 && (
        <div className="flex-shrink-0 border-t border-gray-200 bg-gray-50 p-2">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-medium text-gray-500">Thread Artifacts</span>
            <span className="text-xs text-gray-400">{unassociatedArtifacts.length} item(s)</span>
          </div>
          <div className="overflow-x-auto pb-1">
            <div className="flex gap-2">
              {unassociatedArtifacts.map((artifact, idx) => (
                <a
                  key={idx}
                  href={`cursor://file/${artifact.path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-shrink-0 text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-full 
                           hover:bg-blue-50 hover:border-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-300"
                >
                  {artifact.name || `Artifact ${idx + 1}`}
                </a>
              ))}
            </div>
          </div>
        </div>
      )}
      
      {/* Input area - fixed at bottom */}
      <div className="flex-shrink-0 border-t border-gray-200 p-3 bg-white">
        <div className="flex gap-2">
          <input
            type="text"
            className={`flex-1 border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
              isLoading ? "bg-gray-100 cursor-not-allowed" : ""
            }`}
            placeholder={isLoading ? "Waiting for response..." : "Type your message..."}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !isLoading) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading}
            className={`px-4 py-2 rounded font-medium ${
              isLoading
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700 text-white"
            }`}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
};
