import React from 'react';

interface StatusBarProps {
  isLoading: boolean;
  statusMessage: string;
}

export const StatusBar: React.FC<StatusBarProps> = ({ isLoading, statusMessage }) => {
  return (
    <div className="h-full w-full flex items-center px-3 bg-gray-50">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${isLoading ? 'bg-blue-500 animate-pulse' : 'bg-green-500'}`} />
        <span className="text-xs text-gray-600">{statusMessage}</span>
      </div>
    </div>
  );
};
