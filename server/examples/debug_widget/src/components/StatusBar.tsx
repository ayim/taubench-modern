import React, { useState } from 'react';

interface StatusBarProps {
  isLoading: boolean;
  statusMessage: string;
  errorHistory: any[];
}

export const StatusBar: React.FC<StatusBarProps> = ({ isLoading, statusMessage, errorHistory }) => {
  const [showErrors, setShowErrors] = useState(false);
  const recentErrors = errorHistory.slice(-5); // Show last 5 errors
  const hasErrors = errorHistory.length > 0;

  return (
    <div className="h-full w-full flex items-center px-3 bg-gray-50 relative">
      <div className="flex items-center gap-2 flex-1">
        <div className={`w-2 h-2 rounded-full ${isLoading ? 'bg-blue-500 animate-pulse' : 'bg-green-500'}`} />
        <span className="text-xs text-gray-600">{statusMessage}</span>

        {hasErrors && (
          <button
            onClick={() => setShowErrors(!showErrors)}
            className={`text-xs px-2 py-0.5 rounded ml-2 ${
              showErrors ? 'bg-red-200 text-red-800' : 'bg-red-100 text-red-600'
            } hover:bg-red-200`}
          >
            {errorHistory.length} error{errorHistory.length !== 1 ? 's' : ''}
          </button>
        )}
      </div>

      {/* Error panel */}
      {showErrors && hasErrors && (
        <div className="absolute bottom-8 left-0 right-0 bg-white border border-gray-300 shadow-lg max-h-64 overflow-y-auto z-10">
          <div className="p-2 border-b bg-red-50">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-red-800">Recent Errors</span>
              <button onClick={() => setShowErrors(false)} className="text-red-600 hover:text-red-800 text-xs">
                ✕
              </button>
            </div>
          </div>
          <div className="p-2 space-y-2">
            {recentErrors.reverse().map((error, idx) => (
              <div key={idx} className="border-l-2 border-red-400 pl-2 py-1">
                <div className="text-xs text-gray-500">{new Date(error.timestamp).toLocaleString()}</div>
                <div className="text-sm text-red-700 font-medium">{error.error_message}</div>
                <div className="text-xs text-gray-600">
                  Thread: {error.thread_id} | Run: {error.run_id}
                </div>
                {error.error_stack_trace && (
                  <details className="mt-1">
                    <summary className="text-xs text-gray-500 cursor-pointer">Stack Trace</summary>
                    <pre className="text-xs bg-gray-100 p-1 mt-1 overflow-x-auto">{error.error_stack_trace}</pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
