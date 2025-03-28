import React from "react";
import ChatIcon from '@mui/icons-material/Chat';
import DeleteIcon from '@mui/icons-material/Delete';

interface Thread {
  thread_id: string;
  name?: string;
}

interface ThreadsPanelProps {
  threads: Thread[];
  selectedThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onNewThread: () => void;
  onDeleteThread: (threadId: string) => void;
}

export const ThreadsPanel: React.FC<ThreadsPanelProps> = ({
  threads,
  selectedThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
}) => {
  return (
    <div className="w-60 flex flex-col border-r border-gray-200 bg-gray-50 overflow-hidden">
      <div className="p-3 border-b border-gray-200 bg-white">
        <h2 className="font-semibold text-gray-700 mb-2 flex items-center">
          <ChatIcon className="mr-2" /> Threads
        </h2>
        <button
          onClick={onNewThread}
          className="w-full py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors duration-150 ease-in-out text-sm font-medium"
        >
          New Thread
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {threads.map((thread) => (
          <div
            key={thread.thread_id}
            className={`
              px-3 py-2.5 cursor-pointer hover:bg-blue-50 
              ${selectedThreadId === thread.thread_id ? "bg-blue-100" : ""}
              flex justify-between items-center
            `}
          >
            <div 
              onClick={() => onSelectThread(thread.thread_id)}
              className="text-sm font-medium text-gray-800 truncate flex-grow"
            >
              {thread.name || "Unnamed Thread"}
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDeleteThread(thread.thread_id);
              }}
              className="text-red-500 hover:text-red-700 ml-2 p-1 text-xs"
              title="Delete thread"
            >
              <DeleteIcon fontSize="small" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
