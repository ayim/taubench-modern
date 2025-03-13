import React, { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "agent";
  content: any[]; // For agent messages with structured content
}

// User message component
const UserMessage: React.FC<{ content?: any[] }> = ({ content }) => (
  <div className="flex justify-end">
    <div 
      className="px-4 py-2 rounded-lg max-w-[70%] bg-blue-600 text-white"
      style={{ whiteSpace: "pre-wrap" }}
    >
      {content?.[0]?.text}
    </div>
  </div>
);

// Agent message component
const AgentMessage: React.FC<{ content?: any[] }> = ({ content }) => (
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
          }
          return null;
        })}
      </div>
    </div>
  </div>
);

interface ChatPanelProps {
  threadName: string;
  messages: Message[];
  onSendMessage: (text: string) => void;
  isLoading: boolean;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  threadName,
  messages,
  onSendMessage,
  isLoading,
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

  console.log(messages);

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
                <UserMessage content={msg.content} />
              ) : (
                <AgentMessage content={msg.content} />
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>
      
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
