import React from 'react';
import { ThreadsPanel } from './ThreadsPanel';
import { ChatPanel } from './ChatPanel';
import { StatusBar } from './StatusBar';

interface Thread {
  thread_id: string;
  name?: string;
}

interface Message {
  role: 'user' | 'agent';
  content: any[];
  message_id?: string;
}

interface DebugWidgetProps {
  threads: Thread[];
  selected_thread_id: string | null;
  selected_thread_name: string | null;
  messages: Message[];
  is_loading: boolean;
  status_message: string;
  sendMsgToPython: (msg: any) => void; // a generic function that calls widget's send
  active_thread_artifacts: any[];
  error_history: any[];
}

export const DebugWidget: React.FC<DebugWidgetProps> = ({
  threads,
  selected_thread_id,
  selected_thread_name,
  messages,
  is_loading,
  status_message,
  active_thread_artifacts,
  error_history,
  sendMsgToPython,
}) => {
  const handleSelectThread = (threadId: string) => {
    sendMsgToPython({ type: 'select_thread', thread_id: threadId });
  };

  const handleNewThread = () => {
    sendMsgToPython({ type: 'new_thread' });
  };

  const handleSendMessage = (text: string) => {
    sendMsgToPython({ type: 'user_input', text });
  };

  const handleDeleteThread = (threadId: string) => {
    sendMsgToPython({ type: 'delete_thread', thread_id: threadId });
  };

  return (
    <div
      className="w-[800px] h-[800px] border border-gray-300"
      style={{
        display: 'grid',
        gridTemplateRows: 'minmax(0, 1fr) auto',
        overflow: 'hidden',
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
          threadName={selected_thread_name || ''}
          messages={messages}
          onSendMessage={handleSendMessage}
          isLoading={is_loading}
          activeThreadArtifacts={active_thread_artifacts}
        />
      </div>

      {/* Status bar */}
      <div className="w-full h-8 border-t border-gray-200 bg-gray-50">
        <StatusBar isLoading={is_loading} statusMessage={status_message} errorHistory={error_history} />
      </div>
    </div>
  );
};
