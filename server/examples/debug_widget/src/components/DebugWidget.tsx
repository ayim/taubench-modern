import React from "react";
import { ThreadsPanel } from "./ThreadsPanel";
import { ChatPanel } from "./ChatPanel";
import { StatusBar } from "./StatusBar";

interface Thread {
  thread_id: string;
  name?: string;
}

interface Message {
  role: "user" | "agent";
  text: string;
}

interface DebugWidgetProps {
  threads: Thread[];
  selected_thread_id: string | null;
  selected_thread_name: string | null;
  messages: Message[];
  is_loading: boolean;
  status_message: string;
  sendMsgToPython: (msg: any) => void; // a generic function that calls widget's send
}

export const DebugWidget: React.FC<DebugWidgetProps> = ({
  threads,
  selected_thread_id,
  selected_thread_name,
  messages,
  is_loading,
  status_message,
  sendMsgToPython,
}) => {
  const handleSelectThread = (threadId: string) => {
    sendMsgToPython({ type: "select_thread", thread_id: threadId });
  };

  const handleNewThread = () => {
    sendMsgToPython({ type: "new_thread" });
  };

  const handleSendMessage = (text: string) => {
    sendMsgToPython({ type: "user_input", text });
  };

  const handleDeleteThread = (threadId: string) => {
    sendMsgToPython({ type: "delete_thread", thread_id: threadId });
  };

  return (
    <div 
      className="w-[800px] h-[500px] border border-gray-300"
      style={{ 
        display: 'grid',
        gridTemplateRows: 'minmax(0, 1fr) auto',
        overflow: 'hidden'
      }}
    >
      {/* Main content area with thread panel and chat panel */}
      <div className="flex w-full overflow-hidden">
        <ThreadsPanel
          threads={threads}
          selectedThreadId={selected_thread_id}
          onSelectThread={handleSelectThread}
          onNewThread={handleNewThread}
          onDeleteThread={handleDeleteThread}
        />
        <ChatPanel
          threadName={selected_thread_name || ""}
          messages={messages}
          onSendMessage={handleSendMessage}
          isLoading={is_loading}
        />
      </div>
      
      {/* Status bar */}
      <div className="w-full h-8 border-t border-gray-200 bg-gray-50">
        <StatusBar isLoading={is_loading} statusMessage={status_message} />
      </div>
    </div>
  );
};
